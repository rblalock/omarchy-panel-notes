import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons
import "qml"

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property bool closing: false
    property var sourceWindow: null
    property bool saveBlocked: false
    property bool needsResume: false
    property bool retryPending: false
    property var scopes: []
    property int selectedScope: -1
    property var note: null
    property string body: ""
    property string status: ""
    property string failure: ""
    property string page: "note"
    property bool tabBusy: false
    property string tabError: ""
    property string renameTabKey: ""
    property alias tabDialog: addTabDialog
    property alias tabInput: tabName
    readonly property var currentScope: selectedScope >= 0 && selectedScope < scopes.length ? scopes[selectedScope] : null
    property bool preview: false
    property bool externalEditing: false
    property var config: ({})
    property var contentTypes: ({})
    property var notes: []
    property var recoveries: []
    property var callbacks: ({})
    property int requestNumber: 0
    property int generation: 0
    property int saveSequence: 0
    property int pendingSaves: 0
    property var afterSaved: null
    property var pendingOpen: null
    property string socketPath: ""
    QtObject { id: offlineSocket; property bool connected: false }
    property var socket: offlineSocket
    property bool serviceReady: false
    property int reconnectAttempts: 0
    Component.onCompleted: bootstrap.running = true
    property bool observePending: false
    property string collectionRoot: ""
    property real reveal: 0
    property var snapshotJob: null
    readonly property string interfaceVersion: "2026-09-09.17"
    readonly property string pluginId: "io.github.rblalock.panel-notes"
    readonly property var capabilities: note && contentTypes[note.meta.type] && note.meta.formatVersion === contentTypes[note.meta.type].formatVersion ? contentTypes[note.meta.type].capabilities || {} : ({})
    readonly property string executable: decodeURIComponent(Qt.resolvedUrl("panel-notes").toString().replace(/^file:\/\//, ""))
    readonly property var sourceToplevel: sourceWindow ? Hyprland.toplevels.values.filter(function(w) { return "0x" + w.address.replace(/^0x/, "") === sourceWindow.address })[0] : null
    onSourceToplevelChanged: if ((opened || closing) && sourceWindow && sourceWindow.address && !sourceToplevel) close()
    readonly property bool editorFocused: surface.contentItem.Window.window ? surface.contentItem.Window.window.active : false
    property alias editor: editorLoader.item
    property alias panelWindow: surface

    // Public commands work immediately after `omarchy plugin add --enable`.
    IpcHandler {
        target: "panel-notes"
        function toggle(): string { root.open("{}"); return "ok" }
        function library(): string { root.open(JSON.stringify({view:"library"})); return "ok" }
        function hide(): string { root.closeAndReturn(); return "ok" }
        function inspect(): string { return root.inspect() }
    }

    function request(op, args, callback) {
        if (!socket.connected) { failure = "Notes service disconnected. Reopen the panel to reconnect."; return }
        var identity = ++requestNumber
        callbacks[identity] = {op:op, callback:callback || function() {}}
        socket.write(JSON.stringify(Object.assign({ id: identity, op: op }, args || {})) + "\n")
        socket.flush()
    }
    function open(payloadJson) {
        var payload = {}
        try { payload = JSON.parse(payloadJson || "{}") } catch (error) { failure = "Invalid opening request."; return }
        if (opened && editorFocused && !payload.address && !payload.view) { closeAndReturn(); return }
        if (!serviceReady) {
            pendingOpen = payload
            reconnectAttempts = 0
            if (!socket.connected) bootstrap.running = true
            return
        }
        openResolved(payload)
    }
    function openResolved(payload) {
        saveThen(function() {
            var token = ++root.generation
            root.request("open", {address:payload.address || null, library:payload.view === "library"}, function(result) {
                if (token !== root.generation) return
                if (root.opened && root.sourceWindow && result.source.address === root.sourceWindow.address &&
                    JSON.stringify(result.scopes) === JSON.stringify(root.scopes) && !payload.view && !payload.force) {
                    root.closeAndReturn(); return
                }
                root.sourceWindow = result.source
                root.scopes = result.scopes
                root.failure = result.errors.length ? "Some note providers are unavailable." : ""
                root.externalEditing = false
                root.page = payload.view || "note"
                // Remap on explicit retargeting so OnDemand grants opening focus again.
                enterMotion.stop(); exitMotion.stop(); focusRelease.stop()
                root.closing = false; root.opened = false; root.reveal = 0
                Qt.callLater(function() {
                    if (token !== root.generation) return
                    root.opened = true; focusRelease.restart()
                })
                var preferred = (root.config.scopeKeys || {})[result.source.app]
                var index = root.scopes.findIndex(function(scope) { return scope.key === preferred })
                root.selectScope(index >= 0 ? index : Math.max(0, root.scopes.length - 1))
                if (root.page === "library") root.search("")
            })
        })
    }
    function close() {
        focusRelease.stop(); enterMotion.stop(); exitMotion.stop()
        addTabDialog.close(); snapshotJob = null; snapshotTimeout.stop()
        opened = false; closing = false; reveal = 0; generation++; observePending = false
    }
    function dismiss() {
        if (!opened) return
        focusRelease.stop(); enterMotion.stop()
        addTabDialog.close(); snapshotJob = null; snapshotTimeout.stop()
        closing = true; opened = false; generation++; observePending = false
        exitMotion.restart()
    }
    function closeAndReturn() {
        var source = sourceWindow
        dismiss()
        if (source && source.address) request("focus", {source:source})
    }
    function saveThen(callback) {
        if (pendingSaves > 0) afterSaved = callback
        else if (!saveBlocked) callback()
        else failure += " Resolve the saved draft before switching."
    }
    function setNote(value) {
        note = value; body = value.text; saveSequence = 0
        status = "Saved"; failure = ""; externalEditing = false; saveBlocked = false; needsResume = false
        Qt.callLater(function() { if (root.editor && root.page === "note") root.editor.focusEditor() })
    }
    function selectScope(index, remember) {
        if (index < 0 || index >= scopes.length) return
        saveThen(function() {
            if (remember) {
                var preferences = Object.assign({}, root.config.scopeKeys || {})
                preferences[root.sourceWindow.app] = root.scopes[index].key
                root.config = Object.assign({}, root.config, {scopeKeys:preferences})
                root.request("preference", {app:root.sourceWindow.app, key:root.scopes[index].key})
            }
            root.request("scope", {scope:root.scopes[index]}, function(value) { root.setNote(value); root.selectedScope = index })
        })
    }
    function edited(text) {
        if (!note || externalEditing) return
        if (needsResume || !socket.connected) {
            body = text; status = "Not saved"; saveBlocked = true; needsResume = true
            failure = "Connection lost. Your text is here; retry saving."; return
        }
        body = text; status = "Saving…"; pendingSaves++
        var id = note.meta.id
        request("save", {noteId:id, text:text, revision:note.revision, writerId:note.writerId, sequence:++saveSequence}, function(result) {
            root.pendingSaves--
            if (result.conflict) {
                root.failure = result.message
                root.saveBlocked = true
                root.status = "Draft preserved"
                root.afterSaved = null
                root.request("recoveries", {}, function(value) { root.recoveries = value.recoveries })
            } else if (root.note && root.note.meta.id === id) {
                root.note.revision = result.revision
                if (root.pendingSaves === 0) { root.status = "Saved"; root.saveBlocked = false; root.failure = "" }
            }
            if (root.pendingSaves === 0 && root.afterSaved && !result.conflict) {
                var callback = root.afterSaved; root.afterSaved = null; callback()
            }
        })
    }
    function paste() {
        if (!note || !editor) return
        if (!capabilities.images) { editor.pasteText(); return }
        request("clipboard-image", {noteId:note.meta.id}, function(result) {
            if (result.isImage) root.editor.insertAsset(result)
            else root.editor.pasteText()
        })
    }
    function snapshotImage() {
        if (!note || !editor || externalEditing || snapshotJob) return
        if (!sourceToplevel) { failure = "This window cannot be captured."; return }
        snapshotJob = {noteId:note.meta.id, source:Object.assign({}, sourceWindow), target:sourceToplevel.wayland, capturing:false}
        snapshotTimeout.restart()
    }
    function storeSnapshot(view) {
        var job = snapshotJob
        if (!job || job.capturing) return
        job.capturing = true
        job.source.capturedAt = Date.now() / 1000
        request("prepare-capture", {noteId:job.noteId}, function(result) {
            if (root.snapshotJob !== job) return
            var accepted = view.grabToImage(function(image) {
                if (root.snapshotJob !== job) return
                if (!image.saveToFile(result.path)) { root.failure = "Could not save the window image."; root.snapshotJob = null; return }
                root.request("import-capture", {noteId:job.noteId, path:result.path, source:job.source}, function(asset) {
                    if (root.snapshotJob !== job) return
                    if (root.note && root.note.meta.id === job.noteId && root.editor && !root.externalEditing) {
                        root.preview = false
                        root.editor.insertAsset(asset)
                        root.editor.focusEditor()
                    }
                    root.snapshotJob = null
                    snapshotTimeout.stop()
                })
            }, view.sourceSize)
            if (!accepted) { root.failure = "This window could not be captured."; root.snapshotJob = null }
        })
    }
    function showPage(value) {
        page = value
        Qt.callLater(function() {
            if (value === "note" && root.editor) root.editor.focusEditor()
            else if (value === "library") { searchInput.forceActiveFocus(); searchInput.selectAll() }
            else if (value === "settings") folder.forceActiveFocus()
            else if (value === "shortcuts") shortcutList.forceActiveFocus()
        })
        if (value === "library") {
            search(searchInput.text)
            request("recoveries", {}, function(value) { root.recoveries = value.recoveries })
        }
    }
    function cycleScope(delta) {
        if (scopes.length) selectScope((selectedScope + delta + scopes.length) % scopes.length, true)
    }
    function showAddTab() {
        if (!sourceWindow || !sourceWindow.address) return
        renameTabKey = ""; tabError = ""; tabName.text = ""; addTabDialog.open()
    }
    function showRenameTab(scope) {
        if (tabBusy || !scope || !scope.customTab) return
        renameTabKey = scope.key; tabError = ""; tabName.text = scope.label || scope.title
        addTabDialog.open()
    }
    function applyTabs(result) {
        scopes = result.scopes
        var index = scopes.findIndex(function(scope) { return scope.key === result.selectedKey })
        failure = ""
        showPage("note"); selectScope(index >= 0 ? index : 0, true)
    }
    function addTab() {
        if (tabBusy || !sourceWindow || !tabName.text.trim()) return
        if (!socket.connected || saveBlocked) { tabError = "Finish saving your note before changing tabs."; return }
        saveThen(function() {
            root.tabBusy = true; root.tabError = ""
            root.request(root.renameTabKey ? "rename-tab" : "add-tab", {address:root.sourceWindow.address, expected:root.sourceWindow, name:tabName.text.trim(), key:root.renameTabKey}, function(result) {
                root.tabBusy = false; addTabDialog.close(); root.applyTabs(result)
            })
        })
    }
    function removeTab() {
        if (tabBusy || !currentScope || !currentScope.customTab) return
        var key = currentScope.key
        saveThen(function() {
            root.tabBusy = true
            root.request("remove-tab", {address:root.sourceWindow.address, expected:root.sourceWindow, key:key}, function(result) {
                root.tabBusy = false; root.applyTabs(result)
            })
        })
    }
    function search(query) { request("search", {query:query}, function(result) { root.notes = result.notes }) }
    function retrySave() {
        if (!note) return
        if (!socket.connected) { retryPending = true; reconnectAttempts = 0; bootstrap.running = true; return }
        retryPending = false
        externalEditing = true
        request("resume", {noteId:note.meta.id, text:body, revision:note.revision}, function(result) {
            root.externalEditing = false
            if (result.conflict) {
                root.status = "Draft preserved"; root.failure = result.message
                root.request("recoveries", {}, function(value) { root.recoveries = value.recoveries })
                // The draft is now durable, so explicit retargeting is safe.
                root.saveBlocked = false
            } else { root.setNote(result.note); root.needsResume = false }
            if (root.pendingOpen) { var payload = root.pendingOpen; root.pendingOpen = null; root.openResolved(payload) }
        })
    }
    function loadNote(id) { saveThen(function() { root.request("load", {noteId:id}, function(value) {
        root.setNote(value)
        root.selectedScope = root.scopes.findIndex(function(scope) { return scope.key === value.meta.scope.key })
        root.page = "note"
    }) }) }
    function configure(payload) {
        var next = JSON.parse(payload)
        var merged = Object.assign({}, config, next)
        function publish() {
            if (root.shell) root.shell.updateEntryInline(root.pluginId, merged)
            root.config = merged
        }
        if (socket.connected) request("settings-cache", {settings:merged})
        publish()
        return "ok"
    }
    function visibleActions(node) {
        var actions = []
        if (node.shortcut !== undefined && node.text !== undefined) actions.push(node.text)
        for (var child of node.children || []) actions = actions.concat(visibleActions(child))
        return actions
    }
    function inspect() { return JSON.stringify({interfaceVersion:interfaceVersion, loadedPath:Qt.resolvedUrl("Panel.qml").toString(), actions:visibleActions(surface.contentItem), serviceReady:serviceReady, serviceConnected:socket.connected, serviceStarting:bootstrap.running, executable:executable, socketPath:socketPath, opened:opened, source:sourceWindow, scope:selectedScope, noteId:note ? note.meta.id : null, status:status, failure:failure, pendingSaves:pendingSaves, focused:editorFocused, page:page, preview:preview}) }

    Process {
        id: bootstrap
        stderr: StdioCollector { onStreamFinished: if (text.trim()) root.failure = text.trim() }
        command: ["python3", root.executable, "ensure"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.socketPath = JSON.parse(text).socket
                    // Quickshell 0.3.1 retains a failed QLocalSocket internally.
                    // Each explicit bootstrap gets a fresh transport instead of
                    // attempting to reconnect a possibly unusable instance.
                    var previous = root.socket
                    root.socket = socketComponent.createObject(root, {path:root.socketPath})
                    if (previous !== offlineSocket) previous.destroy()
                    root.socket.connected = true
                }
                catch (error) { root.failure = "Could not start the notes service." }
            }
        }
    }
    Component {
        id: socketComponent
        Socket {
            id: bridgeSocket
            onError: {
                if (root.socket !== bridgeSocket) return
                // A socket may disappear between ensure's probe and QML connecting.
                // Retry only an explicit opening/save request, with a bounded budget.
                if ((root.pendingOpen || root.retryPending) && root.reconnectAttempts < 3) {
                    socket.connected = false
                    reconnectDelay.restart()
                }
            }
            parser: SplitParser {
                onRead: function(data) {
                    try {
                        var response = JSON.parse(data), entry = root.callbacks[response.id]
                        delete root.callbacks[response.id]
                        if (!response.ok) {
                            root.failure = response.error
                            if (entry && entry.op === "hello") socket.connected = false
                            if (entry && /^(add-tab|rename-tab|remove-tab)$/.test(entry.op)) { root.tabBusy = false; root.tabError = response.error }
                            if (entry && /^(prepare-capture|import-capture)$/.test(entry.op)) { root.snapshotJob = null; snapshotTimeout.stop() }
                            if (entry && entry.op === "save") {
                                root.status = "Not saved"; root.saveBlocked = true
                                root.pendingSaves = Math.max(0, root.pendingSaves - 1); root.afterSaved = null
                            }
                            if (entry && entry.op === "observe") root.observePending = false
                            if (entry && entry.op === "resume") { root.externalEditing = false; root.status = "Not saved" }
                        } else if (entry) entry.callback(response.result)
                    } catch (error) { root.failure = "Invalid response from the notes service." }
                }
            }
            onConnectionStateChanged: {
                if (root.socket !== bridgeSocket) return
                if (!connected) root.serviceReady = false
                if (connected) root.request("hello", {}, function(result) {
                    root.config = result.settings; root.contentTypes = result.content
                    root.collectionRoot = result.root; root.recoveries = result.recoveries
                    root.serviceReady = true; root.reconnectAttempts = 0
                    if (root.note && (root.needsResume || root.retryPending)) { root.retrySave(); return }
                    if (root.pendingOpen) { var payload = root.pendingOpen; root.pendingOpen = null; root.openResolved(payload) }
                })
                else if (root.note) {
                    root.tabBusy = false
                    root.callbacks = ({}); root.pendingSaves = 0; root.afterSaved = null
                    root.needsResume = true; root.saveBlocked = true; root.observePending = false
                    root.status = "Connection lost"; root.failure = "Your text is here; retry saving to reconnect."
                }
            }
        }
    }
    Timer {
        id: reconnectDelay
        interval: 150
        onTriggered: {
            if (socket.connected || !(root.pendingOpen || root.retryPending)) return
            root.reconnectAttempts++
            bootstrap.running = true
        }
    }
    Timer { id: focusRelease; interval: 16; onTriggered: { if (!root.opened) return; enterMotion.restart(); if (root.editor) root.editor.focusEditor() } }
    NumberAnimation { id: enterMotion; target: root; property: "reveal"; to: 1; duration: root.config.reducedMotion ? 70 : 200; easing.type: Easing.OutCubic }
    NumberAnimation { id: exitMotion; target: root; property: "reveal"; to: 0; duration: root.config.reducedMotion ? 70 : 200; easing.type: Easing.InCubic; onFinished: root.closing = false }
    Timer {
        interval: 180; repeat: true; running: (root.opened || root.closing) && socket.connected && root.sourceWindow !== null && !!root.sourceWindow.address
        onTriggered: {
            if (root.observePending) return
            root.observePending = true
            var token = root.generation
            root.request("observe", {source:root.sourceWindow}, function(result) {
                root.observePending = false
                if (token === root.generation && result.changed) root.close()
            })
        }
    }
    Timer {
        id: snapshotTimeout; interval: 5000
        onTriggered: { if (root.snapshotJob) root.failure = "Window capture timed out. Try Snapshot again."; root.snapshotJob = null }
    }
    PanelWindow {
        id: surface
        visible: root.opened || root.closing
        mask: root.opened ? null : noInput
        Region { id: noInput }
        color: "transparent"
        screen: root.sourceWindow ? Quickshell.screens.filter(function(s) { return s.name === root.sourceWindow.monitor.name })[0] : null
        anchors { top: true; left: true }
        margins.left: root.sourceWindow ? root.sourceWindow.at[0] - root.sourceWindow.monitor.x : 0
        margins.top: root.sourceWindow ? root.sourceWindow.at[1] - root.sourceWindow.monitor.y : 0
        implicitWidth: root.sourceWindow ? root.sourceWindow.size[0] : 700
        implicitHeight: root.sourceWindow ? root.sourceWindow.size[1] : 500
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "panel-notes"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

        Shortcut { sequence: "Escape"; enabled: root.opened && !addTabDialog.opened; context: Qt.WindowShortcut; onActivated: root.closeAndReturn() }
        Shortcut { sequence: "Ctrl+Tab"; enabled: root.opened && root.page === "note" && !addTabDialog.opened; onActivated: root.cycleScope(1) }
        Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: root.opened && root.page === "note" && !addTabDialog.opened; onActivated: root.cycleScope(-1) }
        Shortcut { sequence: "Ctrl+S"; enabled: root.opened && root.page === "note" && !addTabDialog.opened; onActivated: { if (root.needsResume || root.saveBlocked) root.retrySave() } }
        Shortcut { sequence: "F2"; enabled: root.opened && root.page === "note" && !addTabDialog.opened && !root.tabBusy; onActivated: root.showRenameTab(root.currentScope) }
        Popup {
            id: addTabDialog
            parent: surface.contentItem
            anchors.centerIn: parent
            width: Math.min(520, surface.width - Style.space(32))
            modal: true; focus: true
            padding: Style.space(24)
            closePolicy: root.tabBusy ? Popup.NoAutoClose : Popup.CloseOnEscape
            onOpened: { tabName.forceActiveFocus(); tabName.selectAll() }
            onClosed: if (root.editor) root.editor.focusEditor()
            background: Rectangle { color: Color.background; radius: Style.cornerRadius; border.width: 1; border.color: Qt.alpha(Color.accent, .5) }
            Overlay.modal: Rectangle { color: Qt.alpha(Color.background, .75) }
            contentItem: ColumnLayout {
                spacing: Style.space(16)
                Text { text: root.renameTabKey ? "Rename tab" : "Add tab"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body + 4 }
                Text { text: "Name"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body }
                TextField {
                    id: tabName
                    objectName: "tabName"
                    Layout.fillWidth: true
                    placeholderText: "Ideas, Research, To-do…"
                    maximumLength: 120
                    Accessible.name: "Name"
                    enabled: !root.tabBusy
                    color: Color.foreground; placeholderTextColor: Qt.alpha(Color.foreground, .55)
                    selectionColor: Qt.alpha(Color.accent, .3); selectedTextColor: Color.foreground
                    font.family: Style.font.family; font.pixelSize: Style.font.body
                    padding: Style.space(10)
                    background: Rectangle { color: Qt.alpha(Color.foreground, .04); radius: 4; border.width: 1; border.color: tabName.activeFocus ? Color.accent : Qt.alpha(Color.foreground, .2) }
                    onAccepted: root.addTab()
                }
                Text { text: root.tabError; visible: text.length > 0; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Color.urgent; font.pixelSize: Style.font.body }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    Action { text: "Cancel"; enabled: !root.tabBusy; onClicked: addTabDialog.close() }
                    Action { text: root.tabBusy ? "Saving…" : root.renameTabKey ? "Rename" : "Add tab"; selected: true; enabled: !root.tabBusy && tabName.text.trim().length > 0; onClicked: root.addTab() }
                }
            }
        }
        Rectangle {
            id: paper
            objectName: "notesSurface"
            enabled: root.opened && !addTabDialog.opened
            anchors.fill: parent
            color: Color.background
            radius: Style.cornerRadius
            border.width: 1
            border.color: Qt.alpha(Color.accent, .5)
            clip: true
            opacity: root.reveal
            scale: root.config.reducedMotion ? 1 : .99 + root.reveal * .01

            ScreencopyView {
                id: capture
                objectName: "sourceCapture"
                anchors.fill: parent
                captureSource: (root.opened || root.closing) && root.sourceToplevel ? root.sourceToplevel.wayland : null
                live: false
                paintCursor: false
                visible: false
            }
            Loader {
                anchors.fill: parent
                active: root.snapshotJob !== null
                sourceComponent: Component {
                    ScreencopyView {
                        captureSource: root.snapshotJob ? root.snapshotJob.target : null
                        live: false; paintCursor: false; visible: false
                        onHasContentChanged: if (hasContent) root.storeSnapshot(this)
                        onStopped: { if (root.snapshotJob) root.failure = "This window could not be captured."; root.snapshotJob = null }
                    }
                }
            }
            MultiEffect { anchors.fill: parent; source: capture; blurEnabled: true; blurMax: 64; blur: 1; opacity: .035; visible: capture.hasContent && !root.config.reducedMotion }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Style.space(16)
                spacing: Style.space(8)
                RowLayout {
                    Layout.fillWidth: true
                    Text { visible: surface.width > 550; text: root.sourceWindow ? root.sourceWindow.app : "Panel Notes"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body; elide: Text.ElideRight; Layout.fillWidth: true }
                    Action { text: "Notes"; shortcut: "Ctrl+E"; selected: root.page === "note"; onClicked: root.showPage("note") }
                    Action { text: "All notes"; shortcut: "Ctrl+Shift+F"; selected: root.page === "library"; onClicked: root.showPage("library") }
                    Action { text: "Settings"; shortcut: "Ctrl+,"; selected: root.page === "settings"; onClicked: root.showPage("settings") }
                    Action { text: "?"; shortcut: "F1"; Accessible.name: "Keyboard shortcuts"; selected: root.page === "shortcuts"; onClicked: root.showPage("shortcuts") }
                    Action { text: "×"; Accessible.name: "Close notes"; onClicked: root.closeAndReturn() }
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.alpha(Color.foreground, .12) }
                RowLayout {
                    visible: root.page === "note"
                    Layout.fillWidth: true
                    spacing: Style.space(8)
                    Flow {
                        id: scopeTabs
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        spacing: 4
                        Repeater {
                            model: root.scopes
                            Action {
                                required property var modelData
                                required property int index
                                objectName: "scopeTab" + index
                                text: modelData.label || modelData.title
                                shortcut: index < 9 ? "Alt+" + (index + 1) : ""
                                selected: root.selectedScope === index
                                width: Math.min(implicitWidth, 280, scopeTabs.width)
                                tooltip: text + (modelData.customTab ? " · Right-click to rename (F2)" : "")
                                onClicked: root.selectScope(index, true)
                                TapHandler {
                                    acceptedButtons: Qt.RightButton
                                    enabled: modelData.customTab === true && !root.tabBusy
                                    onTapped: root.showRenameTab(modelData)
                                }
                            }
                        }
                        Action { text: "+"; Accessible.name: "Add tab"; tooltip: "Add tab"; shortcut: "Ctrl+T"; enabled: !!root.sourceWindow && !!root.sourceWindow.address && !root.tabBusy; onClicked: root.showAddTab() }
                    }
                    Action { Layout.alignment: Qt.AlignRight | Qt.AlignTop; text: "Remove tab"; tooltip: "Remove tab · Notes stay in All notes"; shortcut: "Ctrl+Shift+Delete"; visible: !!root.currentScope && !!root.currentScope.customTab; enabled: !root.tabBusy; onClicked: root.removeTab() }
                }
                Loader {
                    id: editorLoader
                    visible: root.page === "note"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    source: root.note && root.contentTypes[root.note.meta.type] && root.note.meta.formatVersion === root.contentTypes[root.note.meta.type].formatVersion ? root.contentTypes[root.note.meta.type].editorUrl : ""
                    onLoaded: {
                        item.text = Qt.binding(function() { return root.body })
                        item.baseUrl = Qt.binding(function() { return root.note ? root.note.baseUrl : "" })
                        item.preview = Qt.binding(function() { return root.preview })
                        item.readOnly = Qt.binding(function() { return root.externalEditing })
                        item.edited.connect(function(value) { root.edited(value) })
                        if (item.pasteRequested) item.pasteRequested.connect(function() { root.paste() })
                        if (item.closeRequested) item.closeRequested.connect(function() { root.closeAndReturn() })
                        item.focusEditor()
                    }
                }
                Text { visible: root.page === "note" && root.note !== null && !editorLoader.source.toString(); text: "This content extension is unavailable. Its files are preserved."; color: Color.foreground; wrapMode: Text.Wrap; Layout.fillWidth: true }
                ColumnLayout {
                    visible: root.page === "library"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    TextField {
                        id: searchInput
                        Layout.fillWidth: true
                        placeholderText: "Search your notes"
                        onTextChanged: root.search(text)
                        Keys.onPressed: function(event) {
                            if (event.key === Qt.Key_E && event.modifiers === Qt.ControlModifier) { event.accepted = true; root.showPage("note") }
                        }
                        Keys.onDownPressed: { noteList.forceActiveFocus(); noteList.currentIndex = 0 }
                        onAccepted: if (root.notes.length) root.loadNote(root.notes[0].id)
                    }
                    ListView {
                        id: noteList
                        keyNavigationEnabled: true
                        Keys.onReturnPressed: if (currentIndex >= 0) root.loadNote(root.notes[currentIndex].id)
                        Keys.onEnterPressed: if (currentIndex >= 0) root.loadNote(root.notes[currentIndex].id)
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        model: root.notes
                        delegate: ItemDelegate {
                            required property var modelData
                            width: ListView.view.width
                            highlighted: ListView.isCurrentItem
                            text: modelData.title + "  ·  " + (modelData.scope.app || modelData.scope.kind)
                            onClicked: root.loadNote(modelData.id)
                        }
                    }
                    Repeater {
                        model: root.recoveries
                        Action { required property var modelData; required property int index; shortcut: index < 9 ? "Alt+" + (index + 1) : ""; text: "Recover unsaved draft"; onClicked: root.request("recover", {recoveryId:modelData.recoveryId}, function(value) { root.setNote(value); root.page = "note"; root.request("recoveries", {}, function(result) { root.recoveries = result.recoveries }) }) }
                    }
                }
                ScrollView {
                    visible: root.page === "settings"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; contentWidth: availableWidth
                    ColumnLayout {
                    width: parent.width
                    Text { text: "Notes folder"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body }
                    TextField {
                        id: folder
                        Layout.fillWidth: true
                        text: root.collectionRoot
                        placeholderText: "/home/you/Documents/Panel Notes"
                        Keys.onPressed: function(event) {
                            if (event.key === Qt.Key_E && event.modifiers === Qt.ControlModifier) { event.accepted = true; root.showPage("note") }
                        }
                    }
                    RowLayout {
                        Action { text: "Move collection"; shortcut: "Alt+M"; onClicked: root.saveThen(function() { root.request("collection", {path:folder.text, move:true}, function(value) { root.configure(JSON.stringify(value.settings)); root.collectionRoot = value.root }) }) }
                        Action { text: "Use this folder"; shortcut: "Alt+U"; onClicked: root.saveThen(function() { root.request("collection", {path:folder.text}, function(value) { root.configure(JSON.stringify(value.settings)); root.collectionRoot = value.root; root.note = null; root.body = "" }) }) }
                    }

                    }
                }
                ScrollView {
                    id: shortcutList
                    visible: root.page === "shortcuts"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; contentWidth: availableWidth
                    TextArea {
                        readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                        color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body
                        background: null
                        text: "Keyboard shortcuts\n\nSuper+Alt+N   Open / close notes for the focused app\nEscape   Close and return to source\nCtrl+E   Notes / focus editor\nCtrl+Shift+F   Search all notes\nCtrl+,   Settings\nF1   This shortcut guide\n\nCtrl+T   Add a named note tab\nF2   Rename selected tab (or right-click it)\nCtrl+Shift+Delete   Remove selected custom tab (keep notes)\nAlt+1…9   Select scope tab\nCtrl+Tab / Ctrl+Shift+Tab   Next / previous scope\nCtrl+Shift+P   Preview / edit\nCtrl+Shift+S   Snapshot source window\nCtrl+O   Open in Omawrite / reload note\nCtrl+S   Retry saving (normal edits autosave)\nCtrl+R   Retry a blocked save\n\nCtrl+B / Ctrl+I   Bold / italic\nCtrl+V   Paste text or image\nCtrl+Z / Ctrl+Shift+Z   Undo / redo\nTab / Shift+Tab   Move between controls\nSpace / Enter   Activate focused control\n\nAll notes: type to search, Down then arrows to choose, Enter to open. Alt+1…9 recovers the corresponding draft.\n\nSettings\nAlt+M   Move collection\nAlt+U   Use this folder\n"
                    }
                }
                Text { visible: root.failure.length > 0; text: root.failure; color: Color.urgent; wrapMode: Text.Wrap; Layout.fillWidth: true; font.family: Style.font.family; font.pixelSize: Style.font.body }
                Action { visible: root.needsResume || root.saveBlocked; text: "Retry save"; shortcut: "Ctrl+R"; onClicked: root.retrySave() }
                RowLayout {
                    visible: root.page === "note"
                    Layout.fillWidth: true
                    spacing: Style.space(12)
                    Flow {
                        Layout.fillWidth: true
                        spacing: 4
                        Action { text: root.preview ? "Edit" : "Preview"; shortcut: "Ctrl+Shift+P"; visible: root.capabilities.preview === true; selected: root.preview; onClicked: { root.preview = !root.preview; if (root.editor) root.editor.focusEditor() } }
                        Action { text: root.snapshotJob ? "Capturing…" : "Snapshot"; shortcut: "Ctrl+Shift+S"; visible: root.capabilities.images === true; enabled: root.note !== null && !root.externalEditing && root.snapshotJob === null; onClicked: root.snapshotImage() }
                        Action { text: root.externalEditing ? "Reload note" : "Open in Omawrite"; shortcut: "Ctrl+O"; visible: root.capabilities.omawrite === true; enabled: root.note !== null; onClicked: {
                            if (root.externalEditing) root.loadNote(root.note.meta.id)
                            else root.saveThen(function() { root.request("external", {noteId:root.note.meta.id}, function() { root.externalEditing = true }) })
                        } }
                    }
                    Text { text: root.status; Layout.alignment: Qt.AlignRight | Qt.AlignBottom; Layout.preferredHeight: Style.space(32); verticalAlignment: Text.AlignVCenter; color: Qt.alpha(Color.foreground, .7); font.family: Style.font.family; font.pixelSize: Style.font.caption }
                }
            }
        }
    }
}
