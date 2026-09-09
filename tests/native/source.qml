import QtQuick
import QtQuick.Controls
import Quickshell

ShellRoot {
    FloatingWindow {
        title: "Panel Notes installed acceptance"
        visible: true; implicitWidth: 850; implicitHeight: 650
        color: "#25342b"
        TextArea { anchors.fill: parent; text: "Disposable source for installed Panel Notes"; color: "white"; padding: 30; background: null }
    }
}
