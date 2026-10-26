import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const FIELD_TYPES = [
    { value: "char", label: "Texto" },
    { value: "text", label: "Texto largo" },
    { value: "html", label: "HTML" },
    { value: "integer", label: "Entero" },
    { value: "float", label: "Decimal" },
    { value: "monetary", label: "Monetario" },
    { value: "boolean", label: "Booleano" },
    { value: "date", label: "Fecha" },
    { value: "datetime", label: "Fecha y hora" },
    { value: "selection", label: "Selección" },
    { value: "many2one", label: "Many2one" },
    { value: "one2many", label: "One2many" },
    { value: "many2many", label: "Many2many" },
    { value: "binary", label: "Binario" },
];
const RELATIONAL_TYPES = new Set(["many2one", "one2many", "many2many"]);

function toSlug(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
}

export class ArchNode extends Component {
    static template = "atlas_odoo_studio.ArchNode";
    static props = {
        node: Object,
    };

    setup() {
        this.studio = useService("studio");
        this.state = useState(this.studio.state);
    }

    get isSelected() {
        return this.state.selectedPath === this.props.node.id;
    }

    select() {
        this.studio.selectById(this.props.node.id);
    }
}
ArchNode.components = { ArchNode };

export class StudioEditor extends Component {
    static template = "atlas_odoo_studio.StudioEditor";
    static props = { ...standardActionServiceProps };
    static components = { ArchNode };

    setup() {
        this.studio = useService("studio");
        this.state = useState(this.studio.state);
        this.ui = useState({ panel: "operations" });
        onWillStart(async () => {
            await this.studio.open(this.props.action?.params || {});
        });
    }

    get models() {
        return this.state.bootstrap?.models || [];
    }

    get viewTypes() {
        return this.state.bootstrap?.view_types || [];
    }

    get fieldTypes() {
        return FIELD_TYPES;
    }

    get isRelational() {
        return RELATIONAL_TYPES.has(this.state.newField.ttype);
    }

    get isOne2Many() {
        return this.state.newField.ttype === "one2many";
    }

    get isSelection() {
        return this.state.newField.ttype === "selection";
    }

    get canUndo() {
        return this.state.history.length > 0;
    }

    get canRedo() {
        return this.state.future.length > 0;
    }

    get filteredFields() {
        const term = this.state.fieldSearch.trim().toLowerCase();
        return this.state.fields.filter((field) => {
            if (!term) {
                return true;
            }
            return (
                field.name.toLowerCase().includes(term) ||
                String(field.string || "").toLowerCase().includes(term)
            );
        });
    }

    setPanel(panel) {
        this.ui.panel = panel;
    }

    clearError() {
        this.studio.state.error = "";
    }

    onModelChange(ev) {
        this.studio.load(ev.target.value, this.state.viewType, false);
    }

    onViewTypeChange(viewType) {
        if (viewType === this.state.viewType) {
            return;
        }
        this.studio.load(this.state.model, viewType, false);
    }

    onBaseViewChange(ev) {
        this.studio.load(this.state.model, this.state.viewType, Number(ev.target.value) || false);
    }

    suggestFieldName() {
        const slug = toSlug(this.state.newField.label) || "campo";
        this.state.newField.name = `x_sr_${slug}`;
    }

    suggestModelName() {
        const slug = toSlug(this.state.newModel.label) || "app";
        this.state.newModel.name = `x_sr_${slug}`;
    }

    operationDetails(operation) {
        if (operation.node_xml) {
            return operation.node_xml;
        }
        const entries = Object.entries(operation.attributes || {});
        return entries.map(([key, value]) => `${key}="${value}"`).join(" ");
    }

    save() {
        this.studio.save();
    }

    refresh() {
        this.studio.refresh();
    }

    close() {
        this.studio.close();
    }
}

registry.category("actions").add("atlas_odoo_studio.editor", StudioEditor);
