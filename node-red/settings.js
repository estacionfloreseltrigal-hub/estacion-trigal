module.exports = {
    flowFile: 'flows.json',
    flowFilePretty: true,
    adminAuth: {
        type: "credentials",
        users: [{
            username: "admin_trigal",
            password: "<HASH_BCRYPT>",
            permissions: "*"
        }]
    },
    httpNodeAuth: {user:"admin_trigal",pass:"<HASH_BCRYPT>"},
    uiPort: process.env.PORT || 1880,
    diagnostics: {
        enabled: true,
        ui: true,
    },
    runtimeState: {
        enabled: false,
        ui: false,
    },
    telemetry: {
    },
    logging: {
        console: {
            level: "info",
            metrics: false,
            audit: false
        }
    },
    exportGlobalContextKeys: false,
    externalModules: {
    },
    editorTheme: {
        palette: {
        },
        projects: {
            enabled: false,
            workflow: {
                mode: "manual"
            }
        },
        codeEditor: {
            lib: "monaco",
            options: {
            }
        },
        markdownEditor: {
            mermaid: {
                enabled: true
            }
        },
        multiplayer: {
            enabled: false
        },
    },
    functionExternalModules: true,
    globalFunctionTimeout: 0,
    functionTimeout: 0,
    functionGlobalContext: {
    },
    debugMaxLength: 1000,
    mqttReconnectTime: 15000,
    serialReconnectTime: 15000,
}
