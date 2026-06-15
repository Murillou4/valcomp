import QtQuick

Rectangle {
    id: badge

    property string method: "GET"

    implicitWidth: label.implicitWidth + 18
    implicitHeight: 26
    radius: 7
    color: {
        if (method === "GET") return "#233C38"
        if (method === "POST") return "#3E3422"
        if (method === "PUT") return "#29384A"
        if (method === "DELETE") return "#472A30"
        if (method === "WSS") return "#30334A"
        return "#392F3E"
    }
    border.width: 1
    border.color: {
        if (method === "GET") return "#3E6B62"
        if (method === "POST") return "#735E31"
        if (method === "PUT") return "#466485"
        if (method === "DELETE") return "#81444F"
        if (method === "WSS") return "#545A89"
        return "#66506D"
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: badge.method
        color: "#ECEEF3"
        font.family: "Cascadia Mono"
        font.pixelSize: 10
        font.weight: Font.Bold
        font.letterSpacing: 0.7
    }
}
