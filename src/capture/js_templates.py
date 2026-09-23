# JS inyectado en el navegador para capturar selectores semánticos en caliente
JS_SCRIPT = r"""
(function() {
    if (window.__domCapturerInjected) return;
    window.__domCapturerInjected = true;
    
    function esIdValido(id) {
        if (!id) return false;
        if (id.includes("#")) return false; // IDs con '#' (como SAP WebGUI tree nodes) son altamente dinámicos e inestables en CSS
        if (/^u\d+$/.test(id)) return false; // IDs efímeros de sesión SAP (ej: u2186)
        if (/^\d+$/.test(id)) return false;
        // Reconocer IDs estructurales de SAP WebGUI (coordenadas o pantallas ::)
        if (id.includes("::") || /\[\d+,\d+\]/.test(id)) return true;
        if (id.includes("-") && /\d+/.test(id)) return false;
        if (id.includes("_") && /\d+/.test(id)) return false;
        if (id.startsWith("sap-ui-id")) return false;
        if (id.startsWith("sap-comp")) return false;
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
            if (sibling.nodeType === 1 && sibling.tagName === node.tagName) {
                siblingCount++;
            }
        }
        return '';
    }

    function obtenerSelectorOptimo(el, tipoAccion) {
        let tag = el.tagName.toLowerCase();
        let esExtraccion = (tipoAccion === 'extract');
        
        // 0. Detección nativa de elementos estructurados de SAP WebGUI / ITS
        if (el.id && /\[\d+,\d+\]/.test(el.id)) {
            let mCoord = el.id.match(/\[\d+,\d+\]/);
            if (mCoord) {
                return `${tag}[id*="${mCoord[0]}_c"]`;
            }
        }
        let lsdataVal = el.getAttribute("lsdata");
        if (lsdataVal) {
            let mSlow = lsdataVal.match(/(SLOW_[A-Z0-9_]+\[\d+,\d+\])/);
            if (mSlow) {
                return `${tag}[lsdata*="${mSlow[1]}"]`;
            }
        }
        if (el.id && el.id.includes("::")) {
            let mSuf = el.id.match(/::([^"':\s\]]+)$/);
            if (mSuf) {
                return `[id$="::${mSuf[1]}"]`;
            }
            return `[id="${el.id}"]`;
        }

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
        
        // 7. Clases CSS como último recurso antes de XPath (excluyendo clases hipergenéricas de SAP)
        if (el.className && typeof el.className === "string") {
            let clasesGenSAP = ["lsfield__input", "lsfield", "lsfield__subinput", "lsbutton", "lsbutton--base", "lscontrol", "lscontrol--explicitheight", "lscontrol--valigntop", "lscontrol--valignmiddle"];
            let clases = Array.from(el.classList).filter(c => !c.includes("hover") && !c.includes("active") && !clasesGenSAP.includes(c.toLowerCase())).join(".");
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
            if (type === "file") {
                return `Subida de archivo${desc ? ` "${desc}"` : ""}`;
            }
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

    function obtenerAncestros(el) {
        let ancestros = [];
        try {
            let current = el;
            let maxNivel = 15;
            let nivel = 0;
            while (current && current !== document.documentElement && nivel < maxNivel) {
                let tag = current.tagName ? current.tagName.toLowerCase() : "";
                if (!tag) {
                    current = current.parentElement;
                    continue;
                }
                let idText = current.id ? `#${current.id}` : "";
                
                let clasesList = [];
                if (current.classList && typeof current.classList.forEach === 'function') {
                    current.classList.forEach(c => {
                        if (c && typeof c === 'string' && !c.includes("hover") && !c.includes("active")) {
                            clasesList.push(c);
                        }
                    });
                }
                let classText = clasesList.length > 0 ? "." + clasesList.join(".") : "";
                
                ancestros.push({
                    tagName: current.tagName,
                    id: current.id || "",
                    className: (typeof current.className === "string" ? current.className : ""),
                    descriptor: `${tag}${idText}${classText}`,
                    xpath: obtenerXPath(current),
                    selector_sugerido: obtenerSelectorOptimo(current, 'click'),
                    esObjetivo: (nivel === 0)
                });
                current = current.parentElement;
                nivel++;
            }
        } catch (e) {
            console.error("Error al obtener ancestros:", e);
        }
        return ancestros;
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

            let desc = obtenerDescriptorLegible(el);
            if (tipoAccion === 'key') {
                desc = `Presionar tecla "${valor}" en ${desc}`;
            }

            let datos = {
                tipo_accion: tipoAccion,
                tagName: el.tagName,
                descriptor_legible: desc,
                selector_sugerido: obtenerSelectorOptimo(el, tipoAccion),
                valor: valor,
                id: el.id || "",
                name: el.name || "",
                className: el.className || "",
                type: el.getAttribute("type") || "",
                placeholder: el.getAttribute("placeholder") || "",
                xpath: obtenerXPath(el),
                outerHTML: el.outerHTML || "",
                ancestros: obtenerAncestros(el)
            };
            
            window.registrarAccionDOM(JSON.stringify(datos));
        } catch (err) {
            console.error("Error al registrar acción DOM:", err);
        }
    }

    document.addEventListener('click', (e) => {
        // Ignorar clics sobre el botón flotante de control de atajos
        if (e.target && (e.target.closest('#__dom_capturer_key_toggle') || e.target.closest('[data-capturer-ignore="true"]'))) {
            return;
        }

        let esExtraccion = e.shiftKey || e.ctrlKey || e.altKey;
        let el;
        
        if (esExtraccion) {
            el = e.target;
            e.preventDefault();
            e.stopPropagation();
        } else {
            el = e.target.closest('button, a, input, select, textarea, [role="button"], [role="combobox"], [role="tab"], [role="treeitem"], [role="gridcell"], [role="row"], [role="menuitem"], [role="link"], [tabindex], [onclick]');
            
            if (!el) {
                let current = e.target;
                let depth = 0;
                while (current && current !== document.body && depth < 5) {
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
            let esCombobox = el.getAttribute("role") === "combobox" || (el.className && typeof el.className === "string" && el.className.includes("lsField"));
            if (tag === "input" && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(el.type) && !esCombobox) {
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

    document.addEventListener('keydown', (e) => {
        // 1. Ignorar teclas modificadoras solitarias
        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock', 'NumLock', 'ScrollLock'].includes(e.key)) {
            return;
        }

        // 2. FILTRO ESTRICTO DE EDICIÓN: Nunca capturar Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A, Ctrl+Z
        let atajosEdicion = ['c', 'v', 'x', 'a', 'z', 'y', 'insert'];
        if ((e.ctrlKey || e.metaKey) && atajosEdicion.includes(e.key.toLowerCase())) {
            return;
        }

        // 3. Comprobar si la captura de atajos está habilitada mediante el botón flotante
        let habilitado = false;
        try {
            if (window.top && window.top.__grabarTeclasHabilitado !== undefined) {
                habilitado = window.top.__grabarTeclasHabilitado;
            } else if (window.__grabarTeclasHabilitado !== undefined) {
                habilitado = window.__grabarTeclasHabilitado;
            }
        } catch (err) {}

        let esTeclaFuncion = /^F\d+$/.test(e.key); // F1 a F12 (ej: F4, F8 en SAP)
        let esNavegacion = ['Enter', 'Tab', 'Escape', 'Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End'].includes(e.key);
        let tieneModificador = e.ctrlKey || e.altKey || (e.shiftKey && (esTeclaFuncion || esNavegacion || e.key.length > 1));

        // 4. Si el botón flotante está en OFF, solo capturar Enter y Tab en inputs para confirmación de formularios
        if (!habilitado) {
            if (e.key === 'Enter' || e.key === 'Tab') {
                let el = e.target;
                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.getAttribute('role') === 'combobox')) {
                    enviarAccion(el, 'key', e.key);
                }
            }
            return;
        }

        // 5. Si el botón flotante está en ON, capturar atajos con modificadores y teclas de función (Shift+F4, F8, etc.)
        if (tieneModificador || esTeclaFuncion || e.key === 'Enter' || e.key === 'Escape') {
            let partesMod = [];
            if (e.ctrlKey) partesMod.push('Control');
            if (e.altKey) partesMod.push('Alt');
            if (e.shiftKey) partesMod.push('Shift');
            if (e.metaKey) partesMod.push('Meta');

            let teclaPrincipal = e.key;
            let combinacion = partesMod.length > 0 ? (partesMod.join('+') + '+' + teclaPrincipal) : teclaPrincipal;

            let el = (document.activeElement && document.activeElement !== document.body) ? document.activeElement : (e.target || document.body);
            enviarAccion(el, 'key', combinacion);

            // Notificación visual en el botón flotante
            try {
                if (typeof window.__notificarTeclaCapturada === 'function') {
                    window.__notificarTeclaCapturada(combinacion);
                }
                if (window.top && typeof window.top.__notificarTeclaCapturada === 'function') {
                    window.top.__notificarTeclaCapturada(combinacion);
                }
            } catch (err) {}
        } else if (e.key === 'Tab') {
            let el = e.target;
            if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.getAttribute('role') === 'combobox')) {
                enviarAccion(el, 'key', 'Tab');
            }
        }
    }, true);

    document.addEventListener('change', (e) => {
        let el = e.target;
        let tag = el.tagName.toLowerCase();
        if (tag === "select") {
            let seleccion = el.options[el.selectedIndex].text;
            enviarAccion(el, 'select', seleccion);
        } else if (tag === "input" && el.type === "file") {
            let fileName = (el.files && el.files.length > 0) ? el.files[0].name : (el.value || "");
            enviarAccion(el, 'upload', fileName);
        }
    }, true);

    // Inyección de Botón Flotante ultra-robusto (compatible con SAP WebGUI, Framesets e Iframes)
    function inyectarBotonFlotanteTeclas() {
        if (document.getElementById('__dom_capturer_key_toggle')) return;

        // Comprobar si este frame/ventana debe alojar el botón
        let esFrameset = document.body && document.body.tagName === 'FRAMESET';
        let esTop = (window === window.top);

        if (esTop && esFrameset) {
            // En un frameset superior, los divs no renderizan; permitimos que los iframes interactivos hijos lo alojen
            return;
        }

        if (!esTop) {
            // Si es un iframe: comprobar si top ya tiene el botón visible
            let topTieneBoton = false;
            try {
                if (window.top && window.top.document && window.top.document.getElementById('__dom_capturer_key_toggle')) {
                    topTieneBoton = true;
                }
            } catch (e) {}
            if (topTieneBoton) return;

            // Si top no tiene el botón (ej: frameset de SAP ITS), este frame debe ser visible
            if (window.innerWidth < 250 || window.innerHeight < 150) {
                return;
            }
        }

        if (window.__grabarTeclasHabilitado === undefined) {
            try {
                if (window.top && window.top.__grabarTeclasHabilitado !== undefined) {
                    window.__grabarTeclasHabilitado = window.top.__grabarTeclasHabilitado;
                } else {
                    window.__grabarTeclasHabilitado = false;
                }
            } catch(e) {
                window.__grabarTeclasHabilitado = false;
            }
        }

        let btn = document.createElement('div');
        btn.id = '__dom_capturer_key_toggle';
        btn.setAttribute('data-capturer-ignore', 'true');
        btn.style.cssText = `
            position: fixed !important;
            bottom: 24px !important;
            right: 24px !important;
            z-index: 2147483647 !important;
            padding: 9px 18px !important;
            border-radius: 30px !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            cursor: pointer !important;
            user-select: none !important;
            display: flex !important;
            align-items: center !important;
            gap: 9px !important;
            transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease !important;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4) !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            box-sizing: border-box !important;
            line-height: normal !important;
        `;

        function render(activo, mensajeTemporal) {
            if (mensajeTemporal) {
                btn.style.background = '#0284c7';
                btn.style.color = '#ffffff';
                btn.style.border = '2px solid #38bdf8';
                btn.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ffffff;box-shadow:0 0 8px #ffffff;"></span> ${mensajeTemporal}`;
                return;
            }
            if (activo) {
                btn.style.background = '#065f46';
                btn.style.color = '#ffffff';
                btn.style.border = '2px solid #10b981';
                btn.style.boxShadow = '0 6px 20px rgba(16, 185, 129, 0.45)';
                btn.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#34d399;box-shadow:0 0 8px #34d399;"></span> ⌨️ Grabar Atajos: <span style="color:#a7f3d0;text-decoration:underline;">ON</span>`;
                btn.title = "Detección de atajos ACTIVADA (Shift+F4, F8, etc.). Clic para pausar o arrastra para reubicar.";
            } else {
                btn.style.background = '#0f172a';
                btn.style.color = '#cbd5e1';
                btn.style.border = '2px solid #475569';
                btn.style.boxShadow = '0 6px 20px rgba(0, 0, 0, 0.4)';
                btn.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#64748b;"></span> ⌨️ Grabar Atajos: <strong style="color:#94a3b8;">OFF</strong>`;
                btn.title = "Detección de atajos en PAUSA (no grabará Ctrl+V ni tipeo). Clic para activar Shift+F4 / F8.";
            }
        }

        // Función para cambiar estado y notificar a Python
        function setEstadoTeclas(nuevoEstado) {
            window.__grabarTeclasHabilitado = nuevoEstado;
            try {
                if (window.top) window.top.__grabarTeclasHabilitado = nuevoEstado;
            } catch(e) {}

            render(nuevoEstado);

            // Sincronizar con la app Python
            try {
                if (window.registrarAccionDOM) {
                    window.registrarAccionDOM(JSON.stringify({
                        tipo_accion: "toggle_teclas_estado",
                        habilitado: nuevoEstado
                    }));
                }
            } catch(e) {}
        }

        // Arrastrar (Draggable) para no tapar elementos de SAP WebGUI
        let arrastrando = false;
        let startX = 0, startY = 0, initLeft = 0, initTop = 0;

        btn.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            arrastrando = false;
            startX = e.clientX;
            startY = e.clientY;
            let rect = btn.getBoundingClientRect();
            initLeft = rect.left;
            initTop = rect.top;

            function onMouseMove(me) {
                let dx = me.clientX - startX;
                let dy = me.clientY - startY;
                if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
                    arrastrando = true;
                    btn.style.bottom = 'auto';
                    btn.style.right = 'auto';
                    btn.style.left = Math.max(10, Math.min(window.innerWidth - btn.offsetWidth - 10, initLeft + dx)) + 'px';
                    btn.style.top = Math.max(10, Math.min(window.innerHeight - btn.offsetHeight - 10, initTop + dy)) + 'px';
                }
            }

            function onMouseUp() {
                document.removeEventListener('mousemove', onMouseMove, true);
                document.removeEventListener('mouseup', onMouseUp, true);
            }

            document.addEventListener('mousemove', onMouseMove, true);
            document.addEventListener('mouseup', onMouseUp, true);
        }, true);

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (arrastrando) {
                arrastrando = false;
                return;
            }
            setEstadoTeclas(!window.__grabarTeclasHabilitado);
        }, true);

        // Exponer función de actualización externa para sincronización desde Python
        btn.__actualizarEstado = function(activo) {
            window.__grabarTeclasHabilitado = activo;
            render(activo);
        };
        window.__actualizarBadgeTeclas = function(activo) {
            window.__grabarTeclasHabilitado = activo;
            render(activo);
        };

        window.__notificarTeclaCapturada = function(tecla) {
            render(true, `✅ ¡Atajo "${tecla}" grabado!`);
            setTimeout(() => {
                render(window.__grabarTeclasHabilitado);
            }, 1500);
        };

        render(window.__grabarTeclasHabilitado);

        function anexar() {
            if (document.getElementById('__dom_capturer_key_toggle')) return;
            let container = document.body || document.documentElement;
            if (container && container.tagName === 'FRAMESET') {
                container = document.documentElement;
            }
            if (container) {
                try {
                    container.appendChild(btn);
                } catch(e) {}
            }
        }

        anexar();
        if (document.readyState === 'loading') {
            window.addEventListener('DOMContentLoaded', anexar);
            window.addEventListener('load', anexar);
        }
    }

    inyectarBotonFlotanteTeclas();

    // Verificación periódica para re-inyectar si SAP WebGUI redibuja la pantalla
    setInterval(() => {
        try {
            inyectarBotonFlotanteTeclas();
        } catch(e) {}
    }, 1200);
})();
"""
