import QtQuick
import QtQuick.Controls
import qs.Commons
import "Preview.js" as Preview

Item {
    id: root
    property string text: ""
    property string baseUrl: ""
    property bool preview: false
    property bool readOnly: false
    property alias input: input
    readonly property int bodyFontSize: Math.max(20, Style.font.body)
    readonly property real writingWidth: Math.min(width, 960)
    readonly property real gutter: Math.min(24, Math.max(12, width * .04))
    signal edited(string value)
    signal pasteRequested()
    signal closeRequested()

    function focusEditor() { if (preview) previewScroll.forceActiveFocus(); else input.forceActiveFocus() }
    function insert(value) { input.insert(input.cursorPosition, value) }
    function insertAsset(asset) { insert("\n" + asset.markdown + "\n") }
    function pasteText() { input.paste() }
    function surround(left, right) {
        var start = input.selectionStart, end = input.selectionEnd
        var value = input.selectedText
        input.remove(start, end)
        input.insert(start, left + value + right)
        input.select(start + left.length, start + left.length + value.length)
    }
    function previewBlocks() { return Preview.blocks(root.text) }
    ScrollView {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.writingWidth
        clip: true
        contentWidth: availableWidth
        TextArea {
            id: input
            objectName: "markdownInput"
            visible: !root.preview
            text: root.text
            readOnly: root.readOnly
            selectByMouse: true
            wrapMode: TextEdit.Wrap
            textFormat: TextEdit.PlainText
            color: Color.foreground
            selectionColor: Qt.alpha(Color.accent, .3)
            selectedTextColor: Color.foreground
            placeholderText: "Leave a thought, a question, or a next step…"
            placeholderTextColor: Qt.alpha(Color.foreground, .6)
            font.family: Style.font.family
            font.pixelSize: root.bodyFontSize
            leftPadding: root.gutter; rightPadding: root.gutter
            topPadding: Style.space(24); bottomPadding: Style.space(40)
            background: null
            onTextChanged: if (text !== root.text && !root.readOnly) root.edited(text)
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Tab && !(event.modifiers & Qt.ControlModifier)) { event.accepted = true; input.nextItemInFocusChain(!(event.modifiers & Qt.ShiftModifier)).forceActiveFocus(Qt.TabFocusReason); return }
                if (root.readOnly) return
                if (event.key === Qt.Key_Escape) { event.accepted = true; root.closeRequested() }
                else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_V) { event.accepted = true; root.pasteRequested() }
                else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_B) { event.accepted = true; root.surround("**", "**") }
                else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_I) { event.accepted = true; root.surround("*", "*") }
            }
        }
    }
    ScrollView {
        id: previewScroll
        ScrollBar.vertical: ScrollBar {
            id: previewBar
            policy: ScrollBar.AsNeeded
            background: null
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: Qt.alpha(Color.foreground, previewBar.pressed ? .45 : previewBar.hovered ? .3 : .18)
            }
        }
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.writingWidth
        visible: root.preview
        clip: true
        contentWidth: availableWidth
        Column {
            width: previewScroll.availableWidth
            topPadding: Style.space(24)
            bottomPadding: Style.space(40)
            spacing: Style.space(16)
            Repeater {
                model: root.previewBlocks()
                Loader {
                    required property var modelData
                    width: previewScroll.availableWidth
                    sourceComponent: modelData.kind === "image" ? imageBlock : modelData.kind === "quote" ? quoteBlock : modelData.kind === "code" ? codeBlock : markdownBlock
                }
            }
        }
    }
    Component {
        id: markdownBlock
        TextArea {
            objectName: "previewText"
            text: Preview.markdown(parent.modelData.text)
            baseUrl: root.baseUrl
            textFormat: TextEdit.MarkdownText
            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
            selectionColor: Qt.alpha(Color.accent, .3)
            selectedTextColor: Color.foreground
            color: Color.foreground
            font.family: Style.font.family; font.pixelSize: root.bodyFontSize
            leftPadding: root.gutter; rightPadding: root.gutter
            topPadding: 0; bottomPadding: 0
            background: null
            onLinkActivated: function(link) { if (/^https?:\/\//.test(link)) Qt.openUrlExternally(link) }
        }
    }
    Component {
        id: quoteBlock
        Item {
            implicitHeight: quoteText.implicitHeight + Style.space(28)
            Rectangle {
                anchors.fill: parent
                anchors.leftMargin: root.gutter; anchors.rightMargin: root.gutter
                color: Qt.alpha(Color.accent, .05)
                Rectangle { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 3; color: Qt.alpha(Color.accent, .65) }
            }
            TextArea {
                id: quoteText
                objectName: "previewQuote"
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.leftMargin: root.gutter + Style.space(20); anchors.rightMargin: root.gutter + Style.space(16)
                anchors.topMargin: Style.space(14)
                text: Preview.markdown(parent.parent.modelData.text)
                baseUrl: root.baseUrl
                textFormat: TextEdit.MarkdownText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: Color.foreground
                selectionColor: Qt.alpha(Color.accent, .3); selectedTextColor: Color.foreground
                font.family: Style.font.family; font.pixelSize: root.bodyFontSize
                padding: 0; background: null
                onLinkActivated: function(link) { if (/^https?:\/\//.test(link)) Qt.openUrlExternally(link) }
            }
        }
    }
    Component {
        id: codeBlock
        Item {
            implicitHeight: codeText.implicitHeight + Style.space(32)
            Rectangle {
                anchors.fill: parent
                anchors.leftMargin: root.gutter; anchors.rightMargin: root.gutter
                color: Qt.alpha(Color.foreground, .045)
                border.width: 1; border.color: Qt.alpha(Color.foreground, .09)
                radius: Math.min(6, Style.cornerRadius)
            }
            TextArea {
                id: codeText
                objectName: "previewCode"
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.leftMargin: root.gutter + Style.space(16); anchors.rightMargin: root.gutter + Style.space(16)
                anchors.topMargin: Style.space(16)
                text: parent.parent.modelData.text
                textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: Color.foreground
                selectionColor: Qt.alpha(Color.accent, .3); selectedTextColor: Color.foreground
                font.family: Style.font.family; font.pixelSize: Math.max(16, root.bodyFontSize - 2)
                padding: 0; background: null
            }
        }
    }
    Component {
        id: imageBlock
        Item {
            implicitHeight: picture.status === Image.Ready && picture.sourceSize.width > 0 ? (width - root.gutter * 2) * picture.sourceSize.height / picture.sourceSize.width : 0
            Image {
                id: picture
                anchors.fill: parent
                anchors.leftMargin: root.gutter; anchors.rightMargin: root.gutter
                source: root.baseUrl + parent.parent.modelData.path
                fillMode: Image.PreserveAspectFit
                Accessible.name: parent.parent.modelData.alt
                Accessible.role: Accessible.Graphic
            }
            Rectangle {
                anchors.fill: picture
                color: "transparent"
                border.width: 1
                border.color: Qt.alpha(Color.foreground, .12)
                visible: picture.status === Image.Ready
            }
        }
    }
}
