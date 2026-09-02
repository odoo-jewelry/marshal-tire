import { onMounted } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { ControlPanel } from "@web/search/control_panel/control_panel";

const STORAGE_KEY = "web_chatter_toggle.hidden";
const BODY_CLASS = "o_chatter_globally_hidden";

patch(ControlPanel.prototype, {
    setup() {
        super.setup();
        this.chatterToggleEnabled = Boolean(session.web_chatter_toggle_enabled);
        this.state.chatterHidden =
            this.chatterToggleEnabled &&
            browser.localStorage.getItem(STORAGE_KEY) === "1";
        onMounted(() => {
            document.body.classList.toggle(
                BODY_CLASS,
                this.state.chatterHidden
            );
        });
    },

    get showChatterToggle() {
        // Form views on desktop only, and only when enabled in Settings.
        // Mobile already stacks the chatter below the sheet.
        return (
            this.chatterToggleEnabled &&
            this.env.config?.viewType === "form" &&
            !this.env.isSmall
        );
    },

    toggleGlobalChatter() {
        this.state.chatterHidden = !this.state.chatterHidden;
        browser.localStorage.setItem(
            STORAGE_KEY,
            this.state.chatterHidden ? "1" : "0"
        );
        document.body.classList.toggle(BODY_CLASS, this.state.chatterHidden);
    },
});
