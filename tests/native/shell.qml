import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import "Notes"

ShellRoot {
    id: test
    function captureView(node) {
        if (node.objectName === "sourceCapture") return node
        for (var child of node.children || []) { var found = captureView(child); if (found) return found }
        return null
    }
    property var motionSamples: []
    function sampleMotion() { return {time:Date.now(), reveal:notes.reveal, opened:notes.opened, closing:notes.closing, visible:notes.panelWindow.visible, masked:notes.panelWindow.mask !== null, keyboard:notes.panelWindow.WlrLayershell.keyboardFocus} }
    Connections { target: notes; function onRevealChanged() { test.motionSamples.push(test.sampleMotion()) } }
    property double openingStarted: 0
    property double firstFrameAt: 0
    property double settledAt: 0
    Connections {
        target: notes.panelWindow.contentItem.Window.window
        function onFrameSwapped() {
            if (!test.openingStarted || !notes.opened || notes.reveal <= 0) return
            if (!test.firstFrameAt) test.firstFrameAt = Date.now()
            if (!test.settledAt && notes.reveal === 1) test.settledAt = Date.now()
        }
    }
    Panel { id: notes }
    FloatingWindow {
        id: first
        title: "Panel Notes native source"
        visible: true; implicitWidth: 800; implicitHeight: 650
        color: "#26352b"
        TextArea { id: firstInput; focus: true; anchors.fill: parent; text: "A source document for Panel Notes\n\nThis is disposable native test content."; color: "#eeeeee"; font.pixelSize: 22; padding: 30; background: null }
    }
    FloatingWindow {
        id: second
        property int clicks: 0
        title: "Panel Notes native neighbor"
        visible: true; implicitWidth: 800; implicitHeight: 650
        color: "#293344"
        TextArea {
            id: secondInput; anchors.fill: parent; color: "#eeeeee"; font.pixelSize: 22; padding: 30; background: null
            TapHandler { onTapped: second.clicks++ }
        }
    }
    IpcHandler {
        target: "test"
        function timedOpen(started: string): void {
            test.openingStarted = Number(started); test.firstFrameAt = 0; test.settledAt = 0
            notes.open(JSON.stringify({force:true}))
        }
        function opening(): string { return JSON.stringify({started:test.openingStarted, firstFrame:test.firstFrameAt, settled:test.settledAt, serviceReady:notes.serviceReady}) }
        function open(address: string): void { notes.open(JSON.stringify({address:address, force:true})) }
        function dismiss(): void { test.motionSamples = []; notes.closeAndReturn() }
        function motion(): string { return JSON.stringify({current:test.sampleMotion(), samples:test.motionSamples}) }
        function resetMotion(): void { test.motionSamples = [] }
        function close(): void { notes.close() }
        function state(): string { return JSON.stringify({panel:JSON.parse(notes.inspect()), text:notes.body, editorText:notes.editor ? notes.editor.input.text : "", neighbor:secondInput.text, sourceText:firstInput.text, clicks:second.clicks, capture:notes.sourceToplevel !== null, captureReady:test.captureView(notes.panelWindow.contentItem).hasContent, width:notes.panelWindow.width, height:notes.panelWindow.height}) }
        function snapshot(): void { notes.snapshotImage() }
        function sourceColor(value: string): void { first.color = value }
        function typography(): string { return JSON.stringify({width:notes.editor.width, column:notes.editor.writingWidth, gutter:notes.editor.gutter, font:notes.editor.input.font.pixelSize, x:notes.editor.input.mapToItem(notes.editor,0,0).x}) }
        function edit(value: string): void { notes.editor.input.remove(0, notes.editor.input.length); notes.editor.input.insert(0, value); notes.editor.input.cursorPosition = value.length }
        function rendered(): string {
            var found = []
            function visit(node) {
                if (/^preview(Text|Quote|Code)$/.test(node.objectName || "")) found.push({kind:node.objectName, text:node.getText(0,node.length), lines:node.lineCount, height:node.height})
                for (var child of node.children || []) visit(child)
            }
            visit(notes.editor)
            return JSON.stringify(found)
        }
        function showAddTab(): void { notes.showAddTab() }
        function addTab(value: string): void { notes.tabInput.text = value; notes.addTab() }
        function tabBounds(index: string): string {
            function find(node) {
                if (node.objectName === "scopeTab" + index) {
                    var point = node.mapToItem(notes.panelWindow.contentItem, node.width / 2, node.height / 2)
                    return {x:point.x, y:point.y}
                }
                for (var child of node.children || []) { var found = find(child); if (found) return found }
                return null
            }
            return JSON.stringify(find(notes.panelWindow.contentItem))
        }
        function removeTab(): void { notes.removeTab() }
        function tabs(): string { return JSON.stringify({scopes:notes.scopes, selected:notes.selectedScope, dialog:notes.tabDialog.opened, error:notes.tabError, focus:notes.tabInput.activeFocus}) }
        function settings(): void { notes.showPage("settings") }
        function scopes(): void { notes.scopes = [{kind:"app",key:"test:app",label:"App",title:"Keyboard app"}, {kind:"directory",key:"test:dir",label:"Directory",title:"Keyboard directory"}]; notes.selectScope(0) }
        function preview(): void { notes.preview = !notes.preview }
        function light(): void { Color.background = "#f5f2eb"; Color.foreground = "#242a30"; Color.accent = "#265fba" }
        function reduce(): void { notes.config = {reducedMotion:true} }
        function alternate(): void {
            notes.request('scope', {scope:{key:'example:card:1', kind:'object', title:'Plain content fixture'}, type:'example.plain'}, function(value) { notes.setNote(value) })
        }
        function handoff(): void {
            notes.saveThen(function() { notes.request('external', {noteId:notes.note.meta.id}, function() { notes.externalEditing = true }) })
        }
        function reloadNote(): void { notes.loadNote(notes.note.meta.id) }
        function noCapture(): void { test.captureView(notes.panelWindow.contentItem).captureSource = null }
        function retrySave(): void { notes.retrySave() }
        function quit(): void { Qt.quit() }
    }
}
