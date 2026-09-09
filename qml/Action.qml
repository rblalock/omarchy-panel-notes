import QtQuick
import QtQuick.Controls
import qs.Commons

Button {
    id: control
    property bool selected: false
    property string shortcut: ""
    property string tooltip: text
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip + (shortcut.length ? " · " + shortcut : "")
    ToolTip.delay: 350
    Shortcut {
        sequence: control.shortcut
        context: Qt.WindowShortcut
        enabled: control.visible && control.enabled && control.shortcut.length > 0
        onActivated: control.clicked()
    }
    implicitHeight: Style.space(32)
    implicitWidth: label.implicitWidth + Style.space(20)
    hoverEnabled: true
    contentItem: Text {
        id: label
        text: control.text
        elide: Text.ElideRight
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        color: control.enabled ? (control.selected ? Color.accent : Color.foreground) : Qt.alpha(Color.foreground, .45)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: Math.min(Style.cornerRadius, Style.space(5))
        color: Qt.alpha(Color.foreground, control.down ? .14 : control.hovered || control.selected ? .08 : 0)
        border.width: control.activeFocus ? 1 : 0
        border.color: Color.accent
    }
}
