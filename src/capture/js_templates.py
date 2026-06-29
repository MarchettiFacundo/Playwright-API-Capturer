# JS inyectado en el navegador para capturar selectores semánticos en caliente
JS_SCRIPT = r"""
(function() {
    if (window.__domCapturerInjected) return;
    window.__domCapturerInjected = true;
    
    function esIdValido(id) {
        if (!id) return false;
        if (id.includes("#")) return false; // IDs con '#' (como SAP WebGUI tree nodes) son altamente dinámicos e inestables en CSS
        if (id.includes("-") && /\d+/.test(id)) return false;
        if (id.includes("_") && /\d+/.test(id)) return false;
        if (id.startsWith("sap-ui-id")) return false;
        if (id.startsWith("sap-comp")) return false;
        if (id.includes("::")) return false;
        if (isNaN(id.charAt(0)) === false) return false;
        return true;
    }

    function obtenerXPath(el) {
        if (el.id && esIdValido(el.id)) return `//*[@id="${el.id}"]`;
        if (el === document.body) return '/html/body';
        let siblingCount = 0;
        let siblings = el.parentNode ? el.parentNode.childNodes : [];
        for (let i = 0; i < siblings.length; i++) {
            let sibling = siblings[i];
            if (sibling === el) {
                return obtenerXPath(el.parentNode) + '/' + el.tagName.toLowerCase() + '[' + (siblingCount + 1) + ']';
            }
            if (sibling.nodeType === 1 && sibling.tagName === el.tagName) {
                siblingCount++;
            }
        }
        return '';
    }

    function obtenerSelectorOptimo(el, tipoAccion) {
        let tag = el.tagName.toLowerCase();
        let esExtraccion = (tipoAccion === 'extract');
        
        // 1. Selector por etiqueta asociada (get_by_label)
        let labelText = "";
        if (el.id) {
            let labelEl = document.querySelector(`label[for="${el.id}"]`);
            if (labelEl) labelText = labelEl.textContent.trim();
        }
        if (!labelText) {
            let parentLabel = el.closest('label');
            if (parentLabel) {
                labelText = Array.from(parentLabel.childNodes)
                    .filter(node => node.nodeType === Node.TEXT_NODE)
                    .map(node => node.textContent.trim())
                    .join(" ").trim();
            }
        }
        if (labelText && labelText.length > 0 && labelText.length < 50) {
            return `label="${labelText.replace(/"/g, '\\"')}"`;
        }

        // 2. Selector por placeholder (get_by_placeholder)
        let placeholder = el.getAttribute("placeholder");
        if (placeholder && placeholder.trim().length > 0) {
            return `placeholder="${placeholder.trim().replace(/"/g, '\\"')}"`;
        }
        
        // 3. Selector por rol de accesibilidad (get_by_role)
        let role = el.getAttribute("role");
        if (!role) {
            if (tag === 'button' || (tag === 'input' && ['button', 'submit', 'reset'].includes(el.type))) {
                role = 'button';
            } else if (tag === 'a') {
                role = 'link';
            } else if (tag === 'input' && ['checkbox', 'radio'].includes(el.type)) {
                role = el.type;
            } else if (tag === 'select') {
                role = 'combobox';
            } else if (tag === 'textarea' || (tag === 'input' && ['text', 'email', 'password', 'tel', 'url', 'number', 'search'].includes(el.type))) {
                role = 'textbox';
            } else if (tag.match(/^h[1-6]$/)) {
                role = 'heading';
            }
        }

        if (role) {
            let roleName = "";
            if (role === 'button' || role === 'link' || role === 'heading') {
                if (!esExtraccion) {
                    roleName = el.textContent.trim() || el.value || el.getAttribute("aria-label") || "";
                } else {
                    roleName = el.getAttribute("aria-label") || el.title || "";
                }
            } else if (role === 'textbox') {
                roleName = el.getAttribute("aria-label") || el.title || "";
            }
            roleName = roleName.replace(/\s+/g, ' ').trim();
            if (roleName && roleName.length > 0 && roleName.length < 50) {
                return `role:${role}[name="${roleName.replace(/"/g, '\\"')}_"]`.replace(/_"]$/, '"]');
            }
        }

        // 4. Selector por texto visible corto (get_by_text)
        if (!esExtraccion) {
            let textContent = el.textContent ? el.textContent.trim() : "";
            if ((tag === 'span' || tag === 'div' || tag === 'p' || tag === 'td' || tag === 'th') && textContent.length > 0 && textContent.length < 40) {
                return `text="${textContent.replace(/"/g, '\\"')}"`;
            }
        }

        // 5. IDs estáticos
        if (el.id && esIdValido(el.id)) {
            return `id=${el.id}`;
        }
        
        // 6. Name
        if (el.name) return `[name="${el.name}"]`;
        
        // 7. Clases CSS como último recurso antes de XPath
        if (el.className) {
            let clases = Array.from(el.classList).filter(c => !c.includes("hover") && !c.includes("active")).join(".");
            if (clases) return `${tag}.${clases}`;
        }
        return `xpath=${obtenerXPath(el)}`;
    }

    function obtenerDescriptorLegible(el) {
        let tag = el.tagName.toLowerCase();
        let text = el.textContent ? el.textContent.trim() : "";
        if (text.length > 30) text = text.substring(0, 27) + "...";
        
        if (tag === "button" || el.getAttribute("role") === "button") {
            return `Botón${text ? ` "${text}"` : ""}`;
        }
        if (tag === "a") {
            return `Enlace${text ? ` "${text}"` : ""}`;
        }
        if (tag === "input") {
            let type = el.getAttribute("type") || "text";
            let desc = el.id || el.name || el.getAttribute("placeholder") || "";
            return `Campo ${type}${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "select") {
            let desc = el.id || el.name || "";
            return `Selector${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "textarea") {
            let desc = el.id || el.name || "";
            return `Área de texto${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "td" || tag === "th") {
            return `Celda de tabla${text ? ` "${text}"` : ""}`;
        }
        if (tag === "tr") {
            return `Fila de tabla`;
        }
        if (tag.match(/^h[1-6]$/)) {
            return `Título "${text}"`;
        }
        if (tag === "p") {
            return `Párrafo "${text}"`;
        }
        if (tag === "div" || tag === "span") {
            return `Texto/Contenedor${text ? ` "${text}"` : ""}`;
        }
        return `Elemento <${tag}>${text ? ` "${text}"` : ""}`;
    }

    function enviarAccion(el, tipoAccion, valorOverride) {
        try {
            if (!window.registrarAccionDOM) return;
            
            let tag = el.tagName.toLowerCase();
            let valor = valorOverride !== undefined ? valorOverride : (el.value || "");
            
            if (tipoAccion === 'extract') {
                valor = el.innerText || el.textContent || "";
                valor = valor.trim();
            } else if (tag === "input" && (el.type === "checkbox" || el.type === "radio")) {
                valor = el.checked ? "checked" : "unchecked";
            }

            let datos = {
                tipo_accion: tipoAccion,
                tagName: el.tagName,
                descriptor_legible: obtenerDescriptorLegible(el),
                selector_sugerido: obtenerSelectorOptimo(el, tipoAccion),
                valor: valor,
                id: el.id || "",
                name: el.name || "",
                className: el.className || "",
                type: el.getAttribute("type") || "",
                placeholder: el.getAttribute("placeholder") || "",
                xpath: obtenerXPath(el),
                outerHTML: el.outerHTML || ""
            };
            
            window.registrarAccionDOM(JSON.stringify(datos));
        } catch (err) {
            console.error("Error al registrar acción DOM:", err);
        }
    }

    document.addEventListener('click', (e) => {
        let esExtraccion = e.shiftKey || e.ctrlKey || e.altKey;
        let el;
        
        if (esExtraccion) {
            el = e.target;
            e.preventDefault();
            e.stopPropagation();
        } else {
            el = e.target.closest('button, a, input, select, textarea, [role="button"]');
            
            if (!el) {
                let current = e.target;
                let depth = 0;
                while (current && current !== document.body && depth < 4) {
                    let style = window.getComputedStyle(current);
                    if (style && style.cursor === 'pointer') {
                        el = current;
                        break;
                    }
                    if (current.onclick || current.getAttribute('onclick')) {
                        el = current;
                        break;
                    }
                    current = current.parentElement;
                    depth++;
                }
            }
        }
        
        if (!el) return;
        
        let tag = el.tagName.toLowerCase();
        if (!esExtraccion) {
            if (tag === "input" && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(el.type)) {
                return;
            }
            if (tag === "select" || tag === "textarea") {
                return;
            }
        }
        
        if (esExtraccion) {
            enviarAccion(el, 'extract');
        } else {
            enviarAccion(el, 'click');
        }
    }, true);

    document.addEventListener('input', (e) => {
        let el = e.target;
        let tag = el.tagName.toLowerCase();
        if (tag === "input" && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(el.type)) {
            enviarAccion(el, 'fill');
        } else if (tag === "textarea") {
            enviarAccion(el, 'fill');
        }
    }, true);

    document.addEventListener('change', (e) => {
        let el = e.target;
        let tag = el.tagName.toLowerCase();
        if (tag === "select") {
            let seleccion = el.options[el.selectedIndex].text;
            enviarAccion(el, 'select', seleccion);
        }
    }, true);
})();
"""
