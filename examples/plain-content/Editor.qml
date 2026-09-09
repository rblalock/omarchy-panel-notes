import QtQuick
import QtQuick.Controls
import qs.Commons

Item {
    id: root
    property string text: ""
    property string baseUrl: ""
    property bool preview: false
    property bool readOnly: false
    property alias input: field
    signal edited(string value)
    signal pasteRequested()
    signal closeRequested()
    function focusEditor() { field.forceActiveFocus() }
    function insert(value) { field.insert(field.cursorPosition, value) }
    function pasteText() { field.paste() }
    TextArea {
        id: field; anchors.fill: parent; text: root.text; readOnly: root.readOnly
        textFormat: TextEdit.PlainText; color: Color.foreground; background: null
        onTextChanged: if (text !== root.text) root.edited(text)
        Keys.onEscapePressed: root.closeRequested()
    }
}
