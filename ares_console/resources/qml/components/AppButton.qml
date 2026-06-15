import QtQuick
import QtQuick.Controls

Button {
    id: control

    property bool primary: false
    property bool danger: false

    implicitHeight: 40
    implicitWidth: Math.max(96, contentItem.implicitWidth + 32)
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        color: control.enabled
            ? (control.primary || control.danger ? "#FFF8F8" : "#D8DCE5")
            : "#777C87"
        font.family: "Segoe UI Variable"
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.letterSpacing: 0.8
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 10
        color: {
            if (!control.enabled)
                return "#23262D"
            if (control.down)
                return control.danger ? "#9D3F49" : control.primary ? "#A94F59" : "#31353E"
            if (control.hovered)
                return control.danger ? "#B84D58" : control.primary ? "#C45D68" : "#2B2F37"
            return control.danger ? "#A9444F" : control.primary ? "#B95560" : "#242830"
        }
        border.width: control.primary || control.danger ? 0 : 1
        border.color: "#363B45"

        Behavior on color {
            ColorAnimation { duration: 140 }
        }
    }

    scale: down ? 0.98 : 1
    Behavior on scale {
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }
}
