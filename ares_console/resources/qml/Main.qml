import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Controls.Material
import "components"

ApplicationWindow {
    id: root

    width: 1440
    height: 900
    minimumWidth: 1080
    minimumHeight: 700
    visible: true
    title: "Ares Console"
    color: "#101216"

    Material.theme: Material.Dark
    Material.accent: "#D56A75"
    Material.background: "#101216"
    Material.foreground: "#EEF0F4"

    property string selectedCategory: ""
    property var selectedEndpoint: ({})
    property var variableValues: ({})
    property var queryValues: ({})
    property int valuesRevision: 0
    property bool advancedOpen: false
    property string responseTab: "body"
    property var endpointModel: bridge.filteredEndpoints(searchField.text, selectedCategory)
    property var previewData: {
        valuesRevision
        if (!selectedEndpoint.id)
            return ({ "url": "", "missing": [], "error": "" })
        return bridge.previewRequest(
            selectedEndpoint.id,
            JSON.stringify(variableValues),
            JSON.stringify(queryValues)
        )
    }

    function methodColor(method) {
        if (method === "GET") return "#70B6A8"
        if (method === "POST") return "#D1AE65"
        if (method === "PUT") return "#7BA5D1"
        if (method === "DELETE") return "#D97985"
        if (method === "WSS") return "#989ED8"
        return "#B89BC0"
    }

    function chooseEndpoint(endpoint) {
        selectedEndpoint = endpoint
        variableValues = ({})
        queryValues = ({})
        for (let i = 0; i < endpoint.variables.length; ++i) {
            const name = endpoint.variables[i].name
            variableValues[name] = bridge.defaultValue(name)
        }
        for (let j = 0; j < endpoint.query.length; ++j)
            queryValues[endpoint.query[j].name] = ""
        bodyEditor.text = endpoint.body_example || ""
        headersEditor.text = "{}"
        responseTab = "body"
        valuesRevision += 1
    }

    function executeRequest() {
        bridge.executeEndpoint(
            selectedEndpoint.id,
            JSON.stringify(variableValues),
            JSON.stringify(queryValues),
            bodyEditor.text,
            headersEditor.text
        )
    }

    function requestSend() {
        if (!selectedEndpoint.id || selectedEndpoint.transport !== "http")
            return
        if (selectedEndpoint.mutating)
            confirmDialog.open()
        else
            executeRequest()
    }

    Component.onCompleted: {
        let initial = endpointModel.length > 0 ? endpointModel[0] : ({})
        for (let i = 0; i < endpointModel.length; ++i) {
            if (endpointModel[i].id === "accountXPEndpoint") {
                initial = endpointModel[i]
                break
            }
        }
        if (initial.id)
            chooseEndpoint(initial)
    }

    Connections {
        target: bridge

        function onStreamMessage(message) {
            streamOutput.text += (streamOutput.text.length ? "\n" : "") + message
            streamOutput.cursorPosition = streamOutput.length
        }

        function onSessionChanged() {
            if (!root.selectedEndpoint.id || !root.selectedEndpoint.variables)
                return
            for (let i = 0; i < root.selectedEndpoint.variables.length; ++i) {
                const name = root.selectedEndpoint.variables[i].name
                if (!root.variableValues[name])
                    root.variableValues[name] = bridge.defaultValue(name)
            }
            root.valuesRevision += 1
        }
    }

    Dialog {
        id: confirmDialog
        anchors.centerIn: parent
        width: 480
        modal: true
        title: "Confirmar operação"
        standardButtons: Dialog.Cancel | Dialog.Ok

        contentItem: Text {
            width: 420
            wrapMode: Text.WordWrap
            color: "#D8DCE5"
            text: "Esta rota usa " + (root.selectedEndpoint.method || "") +
                  " e pode alterar dados da conta ou do cliente. Executar mesmo assim?"
        }

        onAccepted: root.executeRequest()
    }

    Rectangle {
        anchors.fill: parent
        color: "#101216"

        Rectangle {
            anchors.fill: parent
            color: "transparent"
            opacity: 0.22

            Canvas {
                anchors.fill: parent
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.strokeStyle = "#242830"
                    ctx.lineWidth = 1
                    for (let x = 0; x < width; x += 48) {
                        ctx.beginPath()
                        ctx.moveTo(x, 0)
                        ctx.lineTo(x, height)
                        ctx.stroke()
                    }
                    for (let y = 0; y < height; y += 48) {
                        ctx.beginPath()
                        ctx.moveTo(0, y)
                        ctx.lineTo(width, y)
                        ctx.stroke()
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            color: "#12151A"
            border.width: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 22
                anchors.rightMargin: 22
                spacing: 16

                Rectangle {
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    radius: 10
                    color: "#B95560"

                    Text {
                        anchors.centerIn: parent
                        text: "A"
                        color: "#FFF8F8"
                        font.family: "Cascadia Mono"
                        font.pixelSize: 18
                        font.bold: true
                    }
                }

                ColumnLayout {
                    spacing: 0

                    Text {
                        text: "ARES CONSOLE"
                        color: "#F3F4F7"
                        font.family: "Segoe UI Variable"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.2
                    }

                    Text {
                        text: bridge.catalogMetadata.endpoint_count + " operações catalogadas"
                        color: "#777E8A"
                        font.pixelSize: 11
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: statusRow.implicitWidth + 24
                    Layout.preferredHeight: 36
                    radius: 11
                    color: "#191C22"
                    border.width: 1
                    border.color: "#2B3038"

                    Row {
                        id: statusRow
                        anchors.centerIn: parent
                        spacing: 9

                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: bridge.session.loading
                                ? "#D1AE65"
                                : bridge.session.online ? "#70B6A8" : "#D97985"

                            SequentialAnimation on opacity {
                                running: bridge.session.loading || bridge.session.online
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.35; duration: 850; easing.type: Easing.InOutSine }
                                NumberAnimation { to: 1; duration: 850; easing.type: Easing.InOutSine }
                            }
                        }

                        Text {
                            text: bridge.session.loading
                                ? "DETECTANDO"
                                : bridge.session.online
                                    ? (bridge.session.region + " / " + bridge.session.shard)
                                    : "OFFLINE"
                            color: "#CED2DA"
                            font.family: "Cascadia Mono"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                    }
                }

                AppButton {
                    text: "ATUALIZAR"
                    enabled: !bridge.session.loading
                    onClicked: bridge.refreshSession()
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: "#252931"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.preferredWidth: 338
                Layout.fillHeight: true
                color: "#13161B"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    TextField {
                        id: searchField
                        Layout.fillWidth: true
                        placeholderText: "Buscar rota, método ou URL"
                        selectByMouse: true
                        leftPadding: 14
                        rightPadding: 14
                        font.pixelSize: 13

                        background: Rectangle {
                            radius: 11
                            color: "#1A1D23"
                            border.width: 1
                            border.color: searchField.activeFocus ? "#6F4A50" : "#2A2E36"
                        }
                    }

                    ListView {
                        id: categoryList
                        Layout.fillWidth: true
                        Layout.preferredHeight: 34
                        orientation: ListView.Horizontal
                        spacing: 7
                        clip: true
                        model: [{ "name": "Todas", "count": bridge.catalogMetadata.endpoint_count }].concat(bridge.categories())

                        delegate: Rectangle {
                            required property var modelData
                            width: categoryLabel.implicitWidth + 22
                            height: 30
                            radius: 9
                            color: {
                                const selected = (modelData.name === "Todas" && root.selectedCategory === "") ||
                                                 root.selectedCategory === modelData.name
                                return selected ? "#302429" : "#1A1D23"
                            }
                            border.width: 1
                            border.color: {
                                const selected = (modelData.name === "Todas" && root.selectedCategory === "") ||
                                                 root.selectedCategory === modelData.name
                                return selected ? "#70464E" : "#2A2E36"
                            }

                            Text {
                                id: categoryLabel
                                anchors.centerIn: parent
                                text: modelData.name + "  " + modelData.count
                                color: "#C8CCD4"
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedCategory = modelData.name === "Todas" ? "" : modelData.name
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true

                        SectionLabel {
                            text: "ROTAS"
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: root.endpointModel.length
                            color: "#656C78"
                            font.family: "Cascadia Mono"
                            font.pixelSize: 11
                        }
                    }

                    ListView {
                        id: endpointList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 5
                        clip: true
                        model: root.endpointModel
                        currentIndex: -1

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        delegate: Rectangle {
                            required property var modelData
                            width: endpointList.width
                            height: 66
                            radius: 11
                            color: root.selectedEndpoint.id === modelData.id
                                ? "#211D22"
                                : endpointMouse.containsMouse ? "#1A1D23" : "transparent"
                            border.width: root.selectedEndpoint.id === modelData.id ? 1 : 0
                            border.color: "#5C3D43"

                            Rectangle {
                                visible: root.selectedEndpoint.id === modelData.id
                                width: 3
                                height: 30
                                radius: 2
                                color: "#D56A75"
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 10
                                spacing: 11

                                MethodBadge {
                                    method: modelData.method
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.name
                                        elide: Text.ElideRight
                                        color: "#E2E5EA"
                                        font.pixelSize: 13
                                        font.weight: Font.Medium
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.category
                                        elide: Text.ElideRight
                                        color: "#737A86"
                                        font.pixelSize: 10
                                    }
                                }
                            }

                            MouseArea {
                                id: endpointMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.chooseEndpoint(modelData)
                            }
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: endpointList.count === 0
                            text: "Nenhuma rota encontrada"
                            color: "#707783"
                        }
                    }
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    width: 1
                    color: "#252931"
                }
            }

            SplitView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                orientation: Qt.Vertical

                ScrollView {
                    id: requestScroll
                    SplitView.fillWidth: true
                    SplitView.fillHeight: true
                    SplitView.minimumHeight: 360
                    clip: true
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: requestScroll.availableWidth
                        spacing: 16

                        Item { Layout.preferredHeight: 6 }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            spacing: 14

                            MethodBadge {
                                method: root.selectedEndpoint.method || "GET"
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    Layout.fillWidth: true
                                    text: root.selectedEndpoint.name || "Selecione uma rota"
                                    color: "#F1F2F5"
                                    font.family: "Segoe UI Variable"
                                    font.pixelSize: 26
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: root.selectedEndpoint.query_name || root.selectedEndpoint.category || ""
                                    color: "#7C838E"
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }

                            AppButton {
                                text: "DOCUMENTAÇÃO"
                                enabled: Boolean(root.selectedEndpoint.docs_url)
                                onClicked: bridge.openUrl(root.selectedEndpoint.docs_url)
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            text: root.selectedEndpoint.description || ""
                            color: "#A7ADB7"
                            wrapMode: Text.WordWrap
                            font.pixelSize: 13
                            lineHeight: 1.25
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            implicitHeight: urlColumn.implicitHeight + 28

                            ColumnLayout {
                                id: urlColumn
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true

                                    SectionLabel { text: "URL RESOLVIDA" }
                                    Item { Layout.fillWidth: true }

                                    Text {
                                        visible: root.previewData.error !== ""
                                        text: "PENDENTE"
                                        color: "#D1AE65"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: root.previewData.url
                                    color: root.previewData.error ? "#C5A96E" : "#D8DCE4"
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 12
                                    wrapMode: Text.WrapAnywhere
                                }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            columns: width > 860 ? 2 : 1
                            columnSpacing: 14
                            rowSpacing: 14

                            Repeater {
                                model: root.selectedEndpoint.variables || []

                                Panel {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: variableColumn.implicitHeight + 24

                                    ColumnLayout {
                                        id: variableColumn
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 7

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Text {
                                                text: modelData.name
                                                color: "#D8DCE4"
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.type
                                                color: "#69717E"
                                                font.family: "Cascadia Mono"
                                                font.pixelSize: 9
                                            }
                                        }

                                        TextField {
                                            Layout.fillWidth: true
                                            text: root.variableValues[modelData.name] || ""
                                            placeholderText: modelData.optional ? "Opcional" : "Obrigatório"
                                            selectByMouse: true
                                            font.family: "Cascadia Mono"
                                            font.pixelSize: 11

                                            onTextEdited: {
                                                root.variableValues[modelData.name] = text
                                                root.valuesRevision += 1
                                            }

                                            background: Rectangle {
                                                radius: 9
                                                color: "#111318"
                                                border.width: 1
                                                border.color: parent.activeFocus ? "#754951" : "#2A2E36"
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            visible: modelData.description !== ""
                                            text: modelData.description
                                            color: "#727986"
                                            wrapMode: Text.WordWrap
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }

                            Repeater {
                                model: root.selectedEndpoint.query || []

                                Panel {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: queryColumn.implicitHeight + 24

                                    ColumnLayout {
                                        id: queryColumn
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 7

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Text {
                                                text: modelData.name
                                                color: "#D8DCE4"
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.optional ? "QUERY OPCIONAL" : "QUERY"
                                                color: modelData.optional ? "#767D89" : "#D1AE65"
                                                font.pixelSize: 9
                                                font.weight: Font.DemiBold
                                            }
                                        }

                                        TextField {
                                            Layout.fillWidth: true
                                            text: root.queryValues[modelData.name] || ""
                                            placeholderText: modelData.description || "Valor"
                                            selectByMouse: true
                                            font.family: "Cascadia Mono"
                                            font.pixelSize: 11

                                            onTextEdited: {
                                                root.queryValues[modelData.name] = text
                                                root.valuesRevision += 1
                                            }

                                            background: Rectangle {
                                                radius: 9
                                                color: "#111318"
                                                border.width: 1
                                                border.color: parent.activeFocus ? "#754951" : "#2A2E36"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            visible: root.selectedEndpoint.body_schema !== null ||
                                     root.selectedEndpoint.transport !== "http"
                            implicitHeight: bodyColumn.implicitHeight + 28

                            ColumnLayout {
                                id: bodyColumn
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 9

                                RowLayout {
                                    Layout.fillWidth: true

                                    SectionLabel {
                                        text: root.selectedEndpoint.transport === "http"
                                            ? "CORPO JSON"
                                            : "PAYLOAD DA CONEXÃO"
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: root.selectedEndpoint.transport === "xmpp" ? "XML BRUTO" : "JSON"
                                        color: "#69717E"
                                        font.family: "Cascadia Mono"
                                        font.pixelSize: 9
                                    }
                                }

                                TextArea {
                                    id: bodyEditor
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 190
                                    wrapMode: TextEdit.NoWrap
                                    selectByMouse: true
                                    color: "#D8DCE4"
                                    selectionColor: "#70434B"
                                    selectedTextColor: "#FFFFFF"
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 11
                                    leftPadding: 12
                                    rightPadding: 12
                                    topPadding: 10
                                    bottomPadding: 10

                                    background: Rectangle {
                                        radius: 10
                                        color: "#101217"
                                        border.width: 1
                                        border.color: bodyEditor.activeFocus ? "#754951" : "#282C34"
                                    }
                                }
                            }
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            implicitHeight: advancedColumn.implicitHeight + 24

                            ColumnLayout {
                                id: advancedColumn
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true

                                    SectionLabel { text: "HEADERS EXTRAS" }
                                    Item { Layout.fillWidth: true }

                                    AppButton {
                                        text: root.advancedOpen ? "RECOLHER" : "ABRIR"
                                        onClicked: root.advancedOpen = !root.advancedOpen
                                    }
                                }

                                TextArea {
                                    id: headersEditor
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: root.advancedOpen ? 110 : 0
                                    visible: root.advancedOpen
                                    text: "{}"
                                    wrapMode: TextEdit.NoWrap
                                    selectByMouse: true
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 11

                                    background: Rectangle {
                                        radius: 9
                                        color: "#101217"
                                        border.width: 1
                                        border.color: "#282C34"
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            Layout.bottomMargin: 22
                            spacing: 10

                            Text {
                                Layout.fillWidth: true
                                text: {
                                    if (!bridge.session.online && root.selectedEndpoint.requirements &&
                                        (root.selectedEndpoint.requirements.token ||
                                         root.selectedEndpoint.requirements.local_auth))
                                        return bridge.session.error
                                    return root.previewData.error
                                }
                                visible: text !== ""
                                color: "#CB7A83"
                                wrapMode: Text.WordWrap
                                font.pixelSize: 11
                            }

                            AppButton {
                                visible: root.selectedEndpoint.transport !== "http" &&
                                         bridge.streamState.state !== "connected"
                                text: bridge.streamState.state === "connecting" ? "CONECTANDO" : "CONECTAR"
                                primary: true
                                enabled: bridge.streamState.state !== "connecting"
                                onClicked: {
                                    streamOutput.text = ""
                                    bridge.connectStream(root.selectedEndpoint.id)
                                }
                            }

                            AppButton {
                                visible: root.selectedEndpoint.transport !== "http" &&
                                         bridge.streamState.state === "connected"
                                text: "DESCONECTAR"
                                danger: true
                                onClicked: bridge.disconnectStream()
                            }

                            AppButton {
                                visible: root.selectedEndpoint.transport !== "http" &&
                                         bridge.streamState.state === "connected"
                                text: "ENVIAR PAYLOAD"
                                primary: true
                                enabled: bodyEditor.text.length > 0
                                onClicked: bridge.sendStream(bodyEditor.text)
                            }

                            AppButton {
                                visible: root.selectedEndpoint.transport === "http"
                                text: bridge.requestRunning ? "EXECUTANDO" : "ENVIAR"
                                primary: true
                                enabled: !bridge.requestRunning && root.previewData.error === ""
                                onClicked: root.requestSend()
                            }
                        }
                    }
                }

                Panel {
                    SplitView.fillWidth: true
                    SplitView.preferredHeight: 300
                    SplitView.minimumHeight: 210
                    radius: 0
                    border.width: 0
                    color: "#111419"

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            color: "#15181E"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 20
                                anchors.rightMargin: 20
                                spacing: 12

                                SectionLabel {
                                    text: root.selectedEndpoint.transport === "http" ? "RESPOSTA" : "STREAM"
                                }

                                Rectangle {
                                    visible: root.selectedEndpoint.transport !== "http"
                                    implicitWidth: streamStatusText.implicitWidth + 18
                                    implicitHeight: 24
                                    radius: 7
                                    color: "#20242B"
                                    border.width: 1
                                    border.color: "#343943"

                                    Text {
                                        id: streamStatusText
                                        anchors.centerIn: parent
                                        text: bridge.streamState.state.toUpperCase()
                                        color: bridge.streamState.state === "connected" ? "#70B6A8" :
                                               bridge.streamState.state === "error" ? "#D97985" : "#A1A7B1"
                                        font.family: "Cascadia Mono"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                    }
                                }

                                Rectangle {
                                    visible: root.selectedEndpoint.transport === "http" &&
                                             bridge.response.status !== undefined
                                    implicitWidth: responseStatus.implicitWidth + 18
                                    implicitHeight: 24
                                    radius: 7
                                    color: bridge.response.ok ? "#223934" : "#42272C"
                                    border.width: 1
                                    border.color: bridge.response.ok ? "#3F6A60" : "#78424A"

                                    Text {
                                        id: responseStatus
                                        anchors.centerIn: parent
                                        text: (bridge.response.status || 0) + " " + (bridge.response.reason || "")
                                        color: "#E6E8EC"
                                        font.family: "Cascadia Mono"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                    }
                                }

                                Text {
                                    visible: root.selectedEndpoint.transport === "http" &&
                                             bridge.response.elapsedMs !== undefined
                                    text: bridge.response.elapsedMs + " ms  /  " + (bridge.response.size || 0) + " bytes"
                                    color: "#737A86"
                                    font.family: "Cascadia Mono"
                                    font.pixelSize: 10
                                }

                                Item { Layout.fillWidth: true }

                                Row {
                                    visible: root.selectedEndpoint.transport === "http" &&
                                             bridge.response.status !== undefined
                                    spacing: 4

                                    Repeater {
                                        model: ["body", "headers"]

                                        Rectangle {
                                            required property string modelData
                                            width: tabText.implicitWidth + 22
                                            height: 28
                                            radius: 8
                                            color: root.responseTab === modelData ? "#29242A" : "transparent"

                                            Text {
                                                id: tabText
                                                anchors.centerIn: parent
                                                text: modelData === "body" ? "CORPO" : "HEADERS"
                                                color: root.responseTab === modelData ? "#E4E6EA" : "#777E89"
                                                font.pixelSize: 10
                                                font.weight: Font.DemiBold
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.responseTab = modelData
                                            }
                                        }
                                    }
                                }

                                AppButton {
                                    visible: responseArea.text.length > 0
                                    text: "COPIAR"
                                    onClicked: bridge.copyText(responseArea.text)
                                }
                            }

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: "#282C34"
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            Column {
                                anchors.centerIn: parent
                                spacing: 10
                                visible: bridge.requestRunning

                                Repeater {
                                    model: 4
                                    Rectangle {
                                        width: 430 - index * 42
                                        height: 12
                                        radius: 6
                                        color: "#282C34"

                                        SequentialAnimation on opacity {
                                            running: bridge.requestRunning
                                            loops: Animation.Infinite
                                            NumberAnimation { to: 0.35; duration: 650 + index * 90 }
                                            NumberAnimation { to: 1; duration: 650 + index * 90 }
                                        }
                                    }
                                }
                            }

                            Column {
                                anchors.centerIn: parent
                                spacing: 6
                                visible: !bridge.requestRunning &&
                                         root.selectedEndpoint.transport === "http" &&
                                         bridge.response.status === undefined

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "A resposta aparecerá aqui"
                                    color: "#7B828E"
                                    font.pixelSize: 14
                                    font.weight: Font.Medium
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "Tokens e cookies sensíveis são ocultados automaticamente."
                                    color: "#565D68"
                                    font.pixelSize: 11
                                }
                            }

                            TextArea {
                                id: streamOutput
                                anchors.fill: parent
                                anchors.margins: 12
                                visible: root.selectedEndpoint.transport !== "http"
                                readOnly: true
                                wrapMode: TextEdit.WrapAnywhere
                                color: "#CED2DA"
                                selectionColor: "#70434B"
                                font.family: "Cascadia Mono"
                                font.pixelSize: 10
                                placeholderText: bridge.streamState.detail

                                background: Rectangle { color: "transparent" }
                            }

                            TextArea {
                                id: responseArea
                                anchors.fill: parent
                                anchors.margins: 12
                                visible: !bridge.requestRunning &&
                                         root.selectedEndpoint.transport === "http" &&
                                         bridge.response.status !== undefined
                                readOnly: true
                                wrapMode: TextEdit.NoWrap
                                text: {
                                    if (bridge.response.error)
                                        return bridge.response.error
                                    if (root.responseTab === "headers")
                                        return JSON.stringify(bridge.response.headers || {}, null, 2)
                                    return bridge.response.body || ""
                                }
                                color: bridge.response.error ? "#D7848D" : "#CED2DA"
                                selectionColor: "#70434B"
                                font.family: "Cascadia Mono"
                                font.pixelSize: 10

                                background: Rectangle { color: "transparent" }
                            }
                        }
                    }
                }
            }
        }
    }
}
