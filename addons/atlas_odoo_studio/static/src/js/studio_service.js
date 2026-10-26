import { reactive } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";

const CONTAINER_TAGS = new Set([
    "div",
    "footer",
    "form",
    "group",
    "header",
    "kanban",
    "list",
    "notebook",
    "page",
    "search",
    "sheet",
]);
const BOOLEAN_ATTRIBUTES = new Set(["invisible", "readonly", "required"]);

function parseXml(arch) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(arch, "application/xml");
    const error = doc.querySelector("parsererror");
    if (error) {
        throw new Error(error.textContent || "XML inválido");
    }
    return doc;
}

function serializeXml(doc) {
    return new XMLSerializer().serializeToString(doc);
}

function parseNodeXml(nodeXml) {
    const doc = parseXml(`<data>${nodeXml}</data>`);
    return Array.from(doc.documentElement.children);
}

function findNode(doc, xpath) {
    const result = doc.evaluate(
        xpath,
        doc,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
    );
    return result.singleNodeValue;
}

function applyOperation(doc, operation) {
    const target = findNode(doc, operation.target_xpath);
    if (!target || target.nodeType !== Node.ELEMENT_NODE) {
        throw new Error(`No se encontró el nodo para ${operation.target_xpath}`);
    }
    if (operation.op_type === "remove_node") {
        target.parentNode.removeChild(target);
        return;
    }
    if (operation.op_type === "set_attribute") {
        for (const [name, value] of Object.entries(operation.attributes || {})) {
            target.setAttribute(name, value);
        }
        return;
    }
    if (operation.op_type === "add_node") {
        const nodes = parseNodeXml(operation.node_xml);
        if (!nodes.length) {
            throw new Error("La operación no contiene nodos.");
        }
        if (operation.position === "inside") {
            for (const node of nodes) {
                target.appendChild(node);
            }
            return;
        }
        if (operation.position === "before") {
            for (const node of nodes) {
                target.parentNode.insertBefore(node, target);
            }
            return;
        }
        if (operation.position === "after") {
            let reference = target.nextSibling;
            for (const node of nodes) {
                target.parentNode.insertBefore(node, reference);
            }
            return;
        }
        if (operation.position === "replace") {
            for (const node of nodes) {
                target.parentNode.insertBefore(node, target);
            }
            target.parentNode.removeChild(target);
            return;
        }
        throw new Error(`Posición no soportada: ${operation.position}`);
    }
    throw new Error(`Operación no soportada: ${operation.op_type}`);
}

function elementIndex(element) {
    let index = 1;
    let sibling = element.previousElementSibling;
    while (sibling) {
        if (sibling.tagName === element.tagName) {
            index++;
        }
        sibling = sibling.previousElementSibling;
    }
    return index;
}

function absoluteXPath(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) {
        return "";
    }
    const parts = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
        const tag = current.tagName;
        const index = elementIndex(current);
        parts.unshift(`${tag}[${index}]`);
        current = current.parentElement;
    }
    return `/${parts.join("/")}`;
}

function buildTree(element, depth, parent = null) {
    const attrs = {};
    for (const attr of Array.from(element.attributes)) {
        attrs[attr.name] = attr.value;
    }
    const id = absoluteXPath(element);
    const node = {
        id,
        tag: element.tagName,
        name: attrs.name || "",
        attrs,
        depth,
        parent,
        children: [],
    };
    for (const child of Array.from(element.children)) {
        node.children.push(buildTree(child, depth + 1, node));
    }
    return node;
}

function findTreeNode(node, id) {
    if (!node) {
        return null;
    }
    if (node.id === id) {
        return node;
    }
    for (const child of node.children) {
        const found = findTreeNode(child, id);
        if (found) {
            return found;
        }
    }
    return null;
}

function clone(value) {
    return value === undefined ? value : JSON.parse(JSON.stringify(value));
}

function errorMessage(error) {
    return error?.data?.message || error?.message || String(error);
}

function parseSelection(text) {
    return String(text || "")
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
            const [value, ...rest] = line.split("|");
            const label = rest.join("|").trim() || value.trim();
            return { value: value.trim(), label };
        });
}

export const studioService = {
    dependencies: ["orm", "dialog", "notification", "action"],
    start(env, { orm, dialog, notification, action }) {
        const service = {
            env,
            orm,
            dialog,
            notification,
            action,
            state: reactive({
                active: false,
                loading: false,
                error: "",
                bootstrap: null,
                model: "",
                modelLabel: "",
                viewType: "form",
                baseViewId: false,
                views: [],
                fields: [],
                operations: [],
                history: [],
                future: [],
                baseArch: "",
                arch: "",
                tree: null,
                selectedPath: "",
                selectedNode: null,
                attrForm: {
                    string: "",
                    required: false,
                    readonly: false,
                    invisible: false,
                    widget: "",
                },
                fieldSearch: "",
                addPosition: "after",
                showNewField: false,
                newField: {
                    label: "",
                    name: "",
                    ttype: "char",
                    relation: "",
                    relationField: "",
                    selectionText: "",
                    required: false,
                    readonly: false,
                },
                showNewModel: false,
                newModel: {
                    label: "",
                    name: "",
                    description: "",
                },
                customization: false,
                dirty: false,
                params: {},
            }),

            notify(message, type = "success") {
                this.notification.add(message, { type });
            },

            async ensureBootstrap() {
                if (this.state.bootstrap) {
                    return;
                }
                this.state.loading = true;
                try {
                    this.state.bootstrap = await this.orm.call(
                        "studio.metadata.service",
                        "get_bootstrap",
                        []
                    );
                } finally {
                    this.state.loading = false;
                }
            },

            async open(params = {}) {
                this.state.active = true;
                this.state.params = params;
                this.state.error = "";
                try {
                    await this.ensureBootstrap();
                } catch (error) {
                    this.state.error = errorMessage(error);
                    return;
                }
                const models = this.state.bootstrap?.models || [];
                const preferred =
                    params.model ||
                    this.state.model ||
                    (models.find((item) => item.model === "res.partner") || models[0] || {}).model;
                if (preferred) {
                    await this.load(preferred, params.viewType || "form", params.viewId || false);
                }
            },

            async load(model, viewType = "form", baseViewId = false) {
                if (!model) {
                    return;
                }
                this.state.loading = true;
                this.state.error = "";
                try {
                    const data = await this.orm.call(
                        "studio.metadata.service",
                        "get_editor_data",
                        [model, viewType, baseViewId || false]
                    );
                    this.state.model = data.model;
                    this.state.modelLabel = data.model_label;
                    this.state.viewType = data.view_type;
                    this.state.baseViewId = data.base_view_id;
                    this.state.views = data.views || [];
                    this.state.fields = data.fields || [];
                    this.state.customization = data.customization || false;
                    this.state.operations = clone(data.operations || []);
                    this.state.baseArch = data.arch || "";
                    this.state.history = [];
                    this.state.future = [];
                    this.state.selectedPath = "";
                    this.state.selectedNode = null;
                    this.state.dirty = false;
                    this.state.showNewField = false;
                    this.state.showNewModel = false;
                    this.rebuild();
                } catch (error) {
                    this.state.error = errorMessage(error);
                } finally {
                    this.state.loading = false;
                }
            },

            rebuild() {
                if (!this.state.baseArch) {
                    return;
                }
                try {
                    const doc = parseXml(this.state.baseArch);
                    for (const operation of this.state.operations) {
                        applyOperation(doc, operation);
                    }
                    this.state.arch = serializeXml(doc);
                    this.state.tree = buildTree(doc.documentElement, 0);
                    const selected = this.state.selectedPath
                        ? findTreeNode(this.state.tree, this.state.selectedPath)
                        : null;
                    this.selectNode(selected);
                } catch (error) {
                    this.state.error = `Error al previsualizar: ${error.message || error}`;
                }
            },

            selectById(id) {
                const node = findTreeNode(this.state.tree, id);
                if (node) {
                    this.selectNode(node);
                }
            },

            selectNode(node) {
                this.state.selectedNode = node || null;
                this.state.selectedPath = node ? node.id : "";
                if (!node) {
                    return;
                }
                this.state.attrForm = {
                    string: node.attrs.string || "",
                    required: node.attrs.required === "1" || node.attrs.required === "True",
                    readonly: node.attrs.readonly === "1" || node.attrs.readonly === "True",
                    invisible:
                        node.attrs.invisible === "1" || node.attrs.invisible === "True",
                    widget: node.attrs.widget || "",
                };
            },

            snapshot() {
                this.state.history.push(clone(this.state.operations));
                this.state.future = [];
            },

            addOperation(operation) {
                this.snapshot();
                this.state.operations.push(operation);
                this.state.dirty = true;
                this.rebuild();
            },

            undo() {
                if (!this.state.history.length) {
                    return;
                }
                this.state.future.push(clone(this.state.operations));
                this.state.operations = this.state.history.pop();
                this.state.dirty = true;
                this.rebuild();
            },

            redo() {
                if (!this.state.future.length) {
                    return;
                }
                this.state.history.push(clone(this.state.operations));
                this.state.operations = this.state.future.pop();
                this.state.dirty = true;
                this.rebuild();
            },

            addField(fieldName) {
                const target = this.state.selectedNode || this.state.tree;
                if (!target) {
                    this.notify("Selecciona un nodo de la vista.", "warning");
                    return;
                }
                let position = this.state.addPosition;
                if (target.depth === 0 && position !== "inside") {
                    position = "inside";
                }
                if (position === "inside" && !CONTAINER_TAGS.has(target.tag)) {
                    position = "after";
                }
                this.addOperation({
                    op_type: "add_node",
                    target_xpath: target.id,
                    position,
                    node_xml: `<field name="${fieldName}"/>`,
                });
            },

            applyAttributes() {
                const node = this.state.selectedNode;
                if (!node) {
                    return;
                }
                const attributes = {};
                const form = this.state.attrForm;
                const keys = ["string", "required", "readonly", "invisible", "widget"];
                for (const key of keys) {
                    let value = form[key];
                    if (BOOLEAN_ATTRIBUTES.has(key)) {
                        value = value ? "1" : "0";
                    }
                    if (String(value) !== String(node.attrs[key] || "")) {
                        attributes[key] = value;
                    }
                }
                if (!Object.keys(attributes).length) {
                    this.notify("No hay cambios de atributos.", "info");
                    return;
                }
                this.addOperation({
                    op_type: "set_attribute",
                    target_xpath: node.id,
                    position: "attributes",
                    attributes,
                });
            },

            removeSelected() {
                const node = this.state.selectedNode;
                if (!node) {
                    return;
                }
                if (node.depth === 0) {
                    this.notify("No se puede eliminar el nodo raíz.", "warning");
                    return;
                }
                this.addOperation({
                    op_type: "remove_node",
                    target_xpath: node.id,
                    position: "replace",
                });
            },

            toggleNewField() {
                this.state.showNewField = !this.state.showNewField;
                this.state.showNewModel = false;
            },

            toggleNewModel() {
                this.state.showNewModel = !this.state.showNewModel;
                this.state.showNewField = false;
            },

            resetNewField() {
                this.state.newField = {
                    label: "",
                    name: "",
                    ttype: "char",
                    relation: "",
                    relationField: "",
                    selectionText: "",
                    required: false,
                    readonly: false,
                };
            },

            async createField() {
                const field = this.state.newField;
                if (!field.label || !field.name) {
                    this.notify("La etiqueta y el nombre técnico son obligatorios.", "warning");
                    return;
                }
                const options = {};
                if (["many2one", "one2many", "many2many"].includes(field.ttype)) {
                    if (!field.relation) {
                        this.notify("Selecciona el modelo relacionado.", "warning");
                        return;
                    }
                    options.relation = field.relation;
                }
                if (field.ttype === "one2many") {
                    if (!field.relationField) {
                        this.notify("Indica el campo many2one inverso.", "warning");
                        return;
                    }
                    options.relation_field = field.relationField;
                }
                if (field.ttype === "selection") {
                    options.selection = parseSelection(field.selectionText);
                }
                if (field.required) {
                    options.required = true;
                }
                if (field.readonly) {
                    options.readonly = true;
                }
                this.state.loading = true;
                try {
                    const created = await this.orm.call(
                        "studio.metadata.service",
                        "create_field",
                        [this.state.model, field.name, field.label, field.ttype],
                        options
                    );
                    this.state.fields.push(created);
                    this.state.fields.sort((a, b) => a.name.localeCompare(b.name));
                    this.state.showNewField = false;
                    this.notify(`Campo ${created.name} creado.`);
                    if (this.state.selectedNode) {
                        this.addField(created.name);
                    }
                    this.resetNewField();
                } catch (error) {
                    this.state.error = errorMessage(error);
                } finally {
                    this.state.loading = false;
                }
            },

            deleteField(fieldId, fieldName) {
                this.dialog.add(ConfirmationDialog, {
                    title: "Eliminar campo",
                    body: `¿Eliminar el campo ${fieldName}? Los datos de la columna se perderán.`,
                    confirmLabel: "Eliminar",
                    confirm: async () => {
                        try {
                            await this.orm.call(
                                "studio.metadata.service",
                                "delete_field",
                                [fieldId]
                            );
                            this.state.fields = this.state.fields.filter(
                                (field) => field.id !== fieldId
                            );
                            this.notify("Campo eliminado.");
                        } catch (error) {
                            this.state.error = errorMessage(error);
                        }
                    },
                });
            },

            async createModel() {
                const model = this.state.newModel;
                if (!model.label) {
                    this.notify("La etiqueta de la app es obligatoria.", "warning");
                    return;
                }
                this.state.loading = true;
                try {
                    const result = await this.orm.call(
                        "studio.metadata.service",
                        "create_model",
                        [model.label],
                        {
                            model_name: model.name || "",
                            description: model.description || "",
                        }
                    );
                    this.state.showNewModel = false;
                    this.state.newModel = { label: "", name: "", description: "" };
                    this.state.bootstrap = null;
                    await this.ensureBootstrap();
                    this.notify(`App ${model.label} creada.`);
                    await this.load(result.model, "form", result.form_view_id);
                } catch (error) {
                    this.state.error = errorMessage(error);
                } finally {
                    this.state.loading = false;
                }
            },

            async save() {
                if (!this.state.model || !this.state.operations.length) {
                    this.notify("No hay cambios para guardar.", "info");
                    return;
                }
                this.state.loading = true;
                this.state.error = "";
                try {
                    const result = await this.orm.call(
                        "studio.metadata.service",
                        "save_customization",
                        [this.state.model, this.state.viewType, this.state.operations],
                        {
                            base_view_id: this.state.baseViewId,
                            customization_id: this.state.customization?.id || false,
                            name:
                                this.state.customization?.name ||
                                `Atlas Studio ${this.state.modelLabel} ${this.state.viewType}`,
                        }
                    );
                    this.state.customization = {
                        id: result.customization_id,
                        name:
                            this.state.customization?.name ||
                            `Atlas Studio ${this.state.modelLabel} ${this.state.viewType}`,
                        version: result.version,
                        state: "applied",
                        extension_view_id: result.extension_view_id,
                    };
                    this.state.dirty = false;
                    this.notify(`Cambios guardados. Versión ${result.version}.`);
                    await this.load(
                        this.state.model,
                        this.state.viewType,
                        this.state.baseViewId
                    );
                } catch (error) {
                    this.state.error = errorMessage(error);
                } finally {
                    this.state.loading = false;
                }
            },

            async refresh() {
                await this.load(this.state.model, this.state.viewType, this.state.baseViewId);
            },

            async close() {
                if (this.state.dirty) {
                    this.dialog.add(ConfirmationDialog, {
                        title: "Cambios sin guardar",
                        body: "Hay cambios sin guardar. ¿Salir de Atlas Studio?",
                        confirmLabel: "Salir",
                        confirm: () => this._leave(),
                    });
                    return;
                }
                await this._leave();
            },

            async _leave() {
                this.state.active = false;
                const previous = this.state.params.previousControllerJsId;
                try {
                    await this.action.restore(previous || undefined);
                } catch {
                    this.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: this.state.model,
                        view_mode: "list,form",
                    });
                }
            },
        };
        return service;
    },
};

registry.category("services").add("studio", studioService);
