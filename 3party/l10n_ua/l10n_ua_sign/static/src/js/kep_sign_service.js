/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Сервіс клієнтського КЕП-підпису поверх бібліотеки IIT EndUser (euscp).
 *
 * Та сама схема, що на cabinet.tax.gov.ua/login: бібліотека працює у
 * web worker браузера, ключ і пароль не залишають клієнт, сервер отримує лише
 * готові підписи. Запити до ЦСК (сертифікати, OCSP) бібліотека робить напряму,
 * якщо ЦСК це дозволяє (directAccess у CAs.json), інакше — через проксі Odoo.
 *
 * Файли бібліотеки пропрієтарні й лежать поза бандлом/git у
 * static/src/lib/euscp (див. README там). Вантажимо їх ЛІНИВО за URL: worker
 * ~17МБ у web.assets_backend роздув би кожну сторінку.
 *
 * Публічне API:
 *   checkLibPresent()   → чи лежать файли (HEAD, без завантаження)
 *   createSigner()      → { readKey(key, pwd), sign(spec), reset() }
 */

export const EUSCP_BASE = "/l10n_ua_sign/static/src/lib/euscp";
export const EUSCP_SCRIPT = `${EUSCP_BASE}/euscp.js`;
export const EUSCP_WORKER = `${EUSCP_BASE}/euscp.worker.js`;
export const CA_SETTINGS_URL = `${EUSCP_BASE}/data/CAs.json`;
export const CA_CERTIFICATES_URL = `${EUSCP_BASE}/data/CACertificates.p7b`;
export const CA_PROXY_URL = "/l10n_ua_sign/ca_proxy";

// EU_ERROR_CERT_NOT_FOUND: ключ виданий не тим ЦСК, що вибрано в діалозі.
export const KEY_CA_MISMATCH = 0x0033;

const REQUIRED_FILES = [EUSCP_SCRIPT, EUSCP_WORKER, CA_SETTINGS_URL, CA_CERTIFICATES_URL];

/** HEAD-перевірка, що файли бібліотеки та ЦСК на місці (без завантаження). */
export async function checkLibPresent() {
    try {
        const responses = await Promise.all(
            REQUIRED_FILES.map((url) => fetch(url, { method: "HEAD" }))
        );
        return responses.every((resp) => resp.ok);
    } catch {
        return false;
    }
}

function loadScript(url) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[data-euscp="${url}"]`)) {
            resolve();
            return;
        }
        const s = document.createElement("script");
        s.src = url;
        s.async = false;
        s.dataset.euscp = url;
        s.onload = () => resolve();
        s.onerror = () => reject(new Error(`Не вдалося завантажити ${url}`));
        document.head.appendChild(s);
    });
}

/**
 * euscp.js — UMD-збірка: підключена звичайним <script>, вона кладе свої
 * експорти (EndUser, EndUserConstants, …) у window.
 */
async function ensureEuscpLoaded() {
    if (!window.EndUser) {
        await loadScript(EUSCP_SCRIPT);
    }
    if (!window.EndUser) {
        throw new Error(_t(
            "Бібліотеку euscp завантажено, але клас EndUser не знайдено — " +
            "перевірте версію файлів у l10n_ua_sign/static/src/lib/euscp."
        ));
    }
}

/**
 * Список ЦСК і їхні сертифікати — у обхід HTTP-кешу браузера.
 *
 * Odoo віддає static із max-age на тиждень: якщо передати бібліотеці URL,
 * після оновлення файлів ЦСК користувачі ще тиждень ініціалізуються зі
 * старими (а несумісний CACertificates.p7b валить Initialize кодом 49,
 * «помилка при роботі з файловим сховищем сертифікатів та СВС»).
 * 'no-cache' перепитує сервер за ETag — незмінений файл коштує лише 304.
 */
async function loadCaData() {
    const load = async (url) => {
        const resp = await fetch(url, { cache: "no-cache" });
        if (!resp.ok) {
            throw new Error(_t("Не вдалося завантажити %s").replace("%s", url));
        }
        return resp;
    };
    const [cas, certificates] = await Promise.all([
        load(CA_SETTINGS_URL).then((resp) => resp.json()),
        load(CA_CERTIFICATES_URL).then((resp) => resp.arrayBuffer()),
    ]);
    return { cas, certificates: new Uint8Array(certificates) };
}

/**
 * ЦСК для вибору в діалозі: ``{name, issuerCNs}``, за назвою.
 *
 * Без вибраного ЦСК бібліотека по черзі перепитує всі ЦСК зі списку, поки
 * не знайде сертифікат ключа, — це довго. ``name`` (перша назва запису) можна
 * передати в ``readKey``: бібліотека шукає ЦСК за будь-якою з ``issuerCNs``.
 */
export async function listCAs() {
    const resp = await fetch(CA_SETTINGS_URL, { cache: "no-cache" });
    if (!resp.ok) {
        return [];
    }
    const cas = await resp.json();
    return cas
        .map((ca) => ({ name: ca.issuerCNs[0], issuerCNs: ca.issuerCNs }))
        .sort((a, b) => a.name.localeCompare(b.name, "uk"));
}

let endUserPromise = null;

/** Один ініціалізований екземпляр EndUser на вкладку (worker дорогий). */
function getEndUser() {
    if (!endUserPromise) {
        endUserPromise = (async () => {
            const [{ cas, certificates }] = await Promise.all([
                loadCaData(),
                ensureEuscpLoaded(),
            ]);
            const libraryTypeJS = window.EndUserConstants?.EndUserLibraryType?.JS ?? 0;
            const eu = new window.EndUser(EUSCP_WORKER, libraryTypeJS);
            await eu.Initialize({
                language: "uk",
                encoding: "UTF-8",
                httpProxyServiceURL: CA_PROXY_URL,
                directAccess: true,
                CAs: cas,
                CACertificates: certificates,
            });
            return eu;
        })().catch((e) => {
            endUserPromise = null;
            throw e;
        });
    }
    return endUserPromise;
}

function b64ToBytes(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) {
        bytes[i] = bin.charCodeAt(i);
    }
    return bytes;
}

/**
 * Підписати один документ у потрібному форматі.
 * Сигнатури — з euscp.d.ts пакета @it-enterprise/digital-signature:
 *   SignDataInternal(appendCert, data, asBase64String)
 *   EnvelopData(recipientsCerts, data, signData, appendCert, asBase64String)
 */
async function signOneDocument(eu, doc) {
    const bytes = b64ToBytes(doc.data_b64);
    const fmt = doc.format || "cades";
    if (fmt === "cades") {
        // CAdES/P7S із вбудованими даними та сертифікатом підписувача.
        return await eu.SignDataInternal(true, bytes, true);
    }
    if (fmt === "envelope") {
        if (!doc.recipient_cert_b64) {
            // Сертифікат шифрування отримувача недоступний — лише підпис.
            return await eu.SignDataInternal(true, bytes, true);
        }
        // Спершу підпис, потім шифрування підписаного на сертифікат отримувача.
        const signedBytes = await eu.SignDataInternal(true, bytes, false);
        return await eu.EnvelopData(
            [b64ToBytes(doc.recipient_cert_b64)], signedBytes, false, true, true
        );
    }
    if (fmt === "asic") {
        if (typeof eu.ASiCSignData === "function") {
            return await eu.ASiCSignData(bytes, true);
        }
        throw new Error(_t("ASiC-підпис недоступний у цій версії бібліотеки."));
    }
    throw new Error(_t("Невідомий формат підпису: %s").replace("%s", fmt));
}

/**
 * Стейтфул-підписувач: тримає зчитаний приватний ключ між кроками
 * (зчитати → підписати → відправити). Ключ і пароль не покидають браузер.
 *
 * Використання:
 *   const signer = createSigner();
 *   const { owner, certs } = await signer.readKey(keyBuffer, password);
 *   const { auth_signature, signed } = await signer.sign(spec);
 *   await signer.reset();   // при закритті діалогу
 */
export function createSigner() {
    let eu = null;
    return {
        get ready() {
            return !!eu;
        },
        /**
         * Крок 1 — зчитати ключ і повернути дані власника (для підтвердження).
         * @param {string|null} caName ЦСК із listCAs(); null — бібліотека
         *     перебирає всі ЦСК (довго). Якщо ключ виданий іншим ЦСК —
         *     помилка з кодом KEY_CA_MISMATCH.
         * @returns {{owner: Object, certs: Array}}
         */
        async readKey(keyBuffer, password, caName = null) {
            if (!keyBuffer) {
                throw new Error(_t("Виберіть файл-ключ (.dat/.jks/.pfx)."));
            }
            if (!password) {
                throw new Error(_t("Введіть пароль до ключа."));
            }
            const lib = await getEndUser();
            eu = null;
            const owner = await lib.ReadPrivateKeyBinary(keyBuffer, password, null, caName || null);
            eu = lib;
            let certs = [];
            try {
                certs = await lib.GetOwnCertificates();
            } catch {
                certs = [];
            }
            return { owner, certs };
        },
        /**
         * Крок 2 — підписати документи вже зчитаним ключем.
         * @param {{auth_subject?: string, documents: Array}} spec
         * @returns {{auth_signature: (string|null), signed: Object}}
         */
        async sign(spec) {
            if (!eu) {
                throw new Error(_t("Спершу зчитайте ключ."));
            }
            let authSignature = null;
            if (spec.auth_subject) {
                authSignature = await eu.SignDataInternal(true, spec.auth_subject, true);
            }
            const signed = {};
            for (const doc of spec.documents || []) {
                signed[doc.name] = await signOneDocument(eu, doc);
            }
            return { auth_signature: authSignature, signed };
        },
        /** Вивантажити ключ із бібліотеки (закриття діалогу). */
        async reset() {
            if (!eu) {
                return;
            }
            const lib = eu;
            eu = null;
            try {
                await lib.ResetPrivateKey();
            } catch {
                // ключ уже вивантажено — нічого робити
            }
        },
    };
}
