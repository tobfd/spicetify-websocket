// Runs the real spicetify-connect-api.js against a fake Spicetify environment and a
// real WebSocket connection, for the end-to-end tests in test_extension_e2e.py.
//
// Usage: node harness.js <extension.js> <server_url> <api_key> <player_data.json>
//
// Writes one JSON line per observable action to stdout and reads control commands
// from stdin (one per line): "songchange", "buffering on", "buffering off", "exit".
"use strict";

const fs = require("node:fs");
const vm = require("node:vm");
const readline = require("node:readline");

const [extensionPath, serverUrl, apiKey, playerDataPath] = process.argv.slice(2);
const emit = (type, data = {}) => process.stdout.write(JSON.stringify({ type, ...data }) + "\n");

// --- Minimal DOM for the settings dialog ------------------------------------
function createElement(tagName) {
    return {
        tagName,
        style: {},
        children: [],
        textContent: "",
        value: "",
        appendChild(child) {
            this.children.push(child);
            return child;
        }
    };
}

// --- Fake Spicetify API ------------------------------------------------------
const playerData = JSON.parse(fs.readFileSync(playerDataPath, "utf8"));
const storage = new Map([
    ["spicetify-connect-api:server_url", serverUrl],
    ["spicetify-connect-api:api_key", apiKey],
    ["spicetify-connect-api:reconnect_interval", "1000"]
]);
const player = { volume: 0.42, heart: true, repeat: 0, shuffle: false, progress: 5000 };
const listeners = {};
const call = (name) => (...args) => emit("call", { name, args });

const Spicetify = {
    Player: {
        data: playerData,
        play: call("play"),
        pause: call("pause"),
        togglePlay: call("togglePlay"),
        next: call("next"),
        back: call("back"),
        seek: call("seek"),
        setVolume: (level) => {
            player.volume = level;
            emit("call", { name: "setVolume", args: [level] });
        },
        setRepeat: call("setRepeat"),
        setShuffle: call("setShuffle"),
        setMute: call("setMute"),
        setHeart: (value) => {
            player.heart = value;
            emit("call", { name: "setHeart", args: [value] });
        },
        getHeart: () => player.heart,
        // Spicetify defines "muted" as volume 0.
        getMute: () => player.volume === 0,
        getProgress: () => player.progress,
        getVolume: () => player.volume,
        isPlaying: () => true,
        getShuffle: () => player.shuffle,
        getRepeat: () => player.repeat,
        playUri: async (uri) => {
            emit("call", { name: "playUri", args: [uri] });
            if (uri.includes("unavailable")) throw new Error("Track unavailable");
        },
        addEventListener: (type, callback) => {
            (listeners[type] = listeners[type] || []).push(callback);
        }
    },
    Platform: {
        PlayerAPI: { seekTo: async (ms) => emit("call", { name: "PlayerAPI.seekTo", args: [ms] }) }
    },
    LocalStorage: {
        get: (key) => (storage.has(key) ? storage.get(key) : null),
        set: (key, value) => storage.set(key, String(value))
    },
    Menu: {
        Item: class {
            register() {}
        }
    },
    PopupModal: { display() {}, hide() {} },
    showNotification: (text, isError) => emit("notification", { text, isError: !!isError }),
    React: {},
    ReactDOM: {},
    URI: {}
};

// A real WebSocket that reports every frame in both directions.
class ObservedWebSocket extends globalThis.WebSocket {
    constructor(url) {
        super(url);
        emit("connect_attempt", { url });
        this.addEventListener("message", (event) => emit("received", { message: JSON.parse(event.data) }));
    }

    send(data) {
        emit("sent", { message: JSON.parse(data) });
        super.send(data);
    }
}

const context = vm.createContext({
    Spicetify,
    window: { Spicetify },
    document: { createElement },
    console: { log() {}, info() {}, warn() {}, error() {} },
    WebSocket: ObservedWebSocket,
    URL,
    Blob,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval
});
vm.runInContext(fs.readFileSync(extensionPath, "utf8"), context, { filename: extensionPath });
emit("loaded");

// --- Control channel ---------------------------------------------------------
readline.createInterface({ input: process.stdin }).on("line", (line) => {
    const [command, argument] = line.trim().split(" ");
    if (command === "songchange") {
        // Like Spotify: a new track starts while buffering, with a different liked state.
        player.heart = !player.heart;
        player.progress = 0;
        (listeners.songchange || []).forEach((callback) => callback({ data: playerData }));
    } else if (command === "buffering") {
        playerData.isBuffering = argument === "on";
    } else if (command === "exit") {
        process.exit(0);
    }
    emit("done", { command: line.trim() });
});
