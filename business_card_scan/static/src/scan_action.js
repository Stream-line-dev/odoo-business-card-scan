/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

// Tesseract.js (OCR open source, licence Apache 2.0) chargé à la demande.
// Le moteur et les langues (fra + eng) sont téléchargés au premier scan
// puis mis en cache par le navigateur.
const TESSERACT_URL = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
const OCR_LANGS = ["eng", "fra"];
const MAX_SIDE = 1600; // px : assez pour l'OCR, léger à envoyer

export class BusinessCardScanAction extends Component {
    static template = "business_card_scan.ScanAction";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.cameraInput = useRef("cameraInput");
        this.fileInput = useRef("fileInput");
        this.video = useRef("video");
        this.stream = null;
        this.state = useState({
            busy: false,
            dragging: false,
            camera: false, // aperçu webcam ouvert (ordinateur)
            cameraReady: false,
            canSwitch: false,
            flash: false,
            step: null, // "engine" | "read" | "save"
            draftCount: 0,
            preview: null,
            message: "",
            progress: 0,
            current: 0,
            total: 0,
        });
        this.steps = [
            { key: "engine", label: _t("OCR engine") },
            { key: "read", label: _t("Reading") },
            { key: "save", label: _t("Saving") },
        ];
        onWillStart(() => this.loadDraftCount());
        onWillUnmount(() => this.stopStream());
        useEffect(
            (videoEl) => {
                if (videoEl && this.stream) {
                    videoEl.srcObject = this.stream;
                }
            },
            () => [this.video.el]
        );
    }

    async loadDraftCount() {
        this.state.draftCount = await this.orm.searchCount("business.card.scan", [
            ["state", "=", "draft"],
            ["user_id", "=", user.userId],
        ]);
    }

    stepStatus(key) {
        const order = this.steps.map((s) => s.key);
        const current = order.indexOf(this.state.step);
        const index = order.indexOf(key);
        if (index < current) {
            return "done";
        }
        return index === current ? "active" : "todo";
    }

    /**
     * Sur mobile, l'attribut `capture` ouvre l'appareil photo natif.
     * Sur ordinateur il est ignoré par les navigateurs (simple sélecteur de
     * fichiers) : on ouvre donc la webcam dans la page via getUserMedia.
     */
    async openCamera() {
        const isTouch = window.matchMedia("(pointer: coarse)").matches;
        if (isTouch || !navigator.mediaDevices?.getUserMedia) {
            if (!isTouch) {
                this.notification.add(
                    _t("Camera is not available here (HTTPS is required). Choose a photo instead."),
                    { type: "warning" }
                );
            }
            this.cameraInput.el.click();
            return;
        }
        try {
            this.facingMode = "environment";
            await this.startStream();
            this.state.camera = true;
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.state.canSwitch = devices.filter((d) => d.kind === "videoinput").length > 1;
        } catch (error) {
            const denied = ["NotAllowedError", "SecurityError"].includes(error.name);
            this.notification.add(
                denied
                    ? _t("Camera access was denied. Allow it in your browser settings, or upload a photo.")
                    : _t("No camera was found. Upload a photo instead."),
                { type: "warning" }
            );
            if (!denied) {
                this.fileInput.el.click();
            }
        }
    }

    async startStream() {
        this.stopStream();
        this.state.cameraReady = false;
        this.stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: this.facingMode,
                width: { ideal: 1920 },
                height: { ideal: 1080 },
            },
            audio: false,
        });
        if (this.video.el) {
            this.video.el.srcObject = this.stream;
        }
    }

    async switchCamera() {
        this.facingMode = this.facingMode === "environment" ? "user" : "environment";
        try {
            await this.startStream();
        } catch {
            this.closeCamera();
        }
    }

    onVideoReady() {
        this.state.cameraReady = true;
    }

    stopStream() {
        this.stream?.getTracks().forEach((track) => track.stop());
        this.stream = null;
    }

    closeCamera() {
        this.stopStream();
        this.state.camera = false;
    }

    capture() {
        const video = this.video.el;
        if (!video?.videoWidth || this.state.flash) {
            return;
        }
        this.state.flash = true;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        canvas.toBlob(
            (blob) => {
                // laisse le temps au flash d'être vu avant de passer à l'analyse
                setTimeout(() => {
                    this.state.flash = false;
                    this.closeCamera();
                    if (blob) {
                        this.processFiles([new File([blob], "card.jpg", { type: "image/jpeg" })]);
                    }
                }, 250);
            },
            "image/jpeg",
            0.92
        );
    }

    openFiles() {
        this.fileInput.el.click();
    }

    onDragOver(ev) {
        ev.preventDefault();
        if (!this.state.busy) {
            this.state.dragging = true;
        }
    }

    onDragLeave(ev) {
        if (!ev.currentTarget.contains(ev.relatedTarget)) {
            this.state.dragging = false;
        }
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.dragging = false;
        this.processFiles([...(ev.dataTransfer?.files || [])]);
    }

    onFilesSelected(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = ""; // permet de re-choisir le même fichier
        this.processFiles(files);
    }

    openHistory() {
        return this.actionService.doAction("business_card_scan.business_card_scan_action");
    }

    async processFiles(allFiles) {
        const files = allFiles.filter((f) => f.type.startsWith("image/"));
        if (allFiles.length && !files.length) {
            this.notification.add(_t("Only images are accepted (JPG, PNG…)."), { type: "warning" });
        }
        if (!files.length || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.total = files.length;
        const scanIds = [];
        let worker;
        try {
            this.state.step = "engine";
            this.state.progress = 0;
            this.state.message = _t("Loading the OCR engine…");
            await loadJS(TESSERACT_URL);
            worker = await window.Tesseract.createWorker(OCR_LANGS, 1, {
                logger: (m) => {
                    if (m.status === "recognizing text") {
                        this.state.progress = Math.round((m.progress || 0) * 100);
                    }
                },
            });
            for (const [index, file] of files.entries()) {
                this.state.current = index + 1;
                this.state.step = "read";
                this.state.progress = 0;
                this.state.message = _t("Reading the card…");
                const dataUrl = await this.prepareImage(file);
                this.state.preview = dataUrl;
                const { data } = await worker.recognize(dataUrl);
                this.state.step = "save";
                this.state.message = _t("Saving…");
                const scanId = await this.orm.call("business.card.scan", "create_from_ocr", [
                    dataUrl.split(",")[1],
                    data.text || "",
                ]);
                scanIds.push(scanId);
            }
        } catch (error) {
            console.error(error);
            this.notification.add(
                _t("Scan failed. Check your internet connection (the OCR engine is downloaded on first use) and try again."),
                { type: "danger" }
            );
        } finally {
            if (worker) {
                await worker.terminate();
            }
            this.state.busy = false;
            this.state.step = null;
            this.state.preview = null;
        }
        if (scanIds.length) {
            this.openScans(scanIds);
        }
    }

    openScans(scanIds) {
        if (scanIds.length === 1) {
            return this.actionService.doAction({
                type: "ir.actions.act_window",
                name: _t("Review Card"),
                res_model: "business.card.scan",
                res_id: scanIds[0],
                views: [[false, "form"]],
                target: "current",
            });
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Cards to Review"),
            res_model: "business.card.scan",
            domain: [["id", "in", scanIds]],
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    /**
     * Redimensionne l'image et la convertit en JPEG (data URL).
     * Une image plus petite = OCR plus rapide sur mobile et envoi plus léger.
     */
    prepareImage(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = reject;
            reader.onload = () => {
                const img = new Image();
                img.onerror = reject;
                img.onload = () => {
                    const ratio = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
                    const canvas = document.createElement("canvas");
                    canvas.width = Math.round(img.width * ratio);
                    canvas.height = Math.round(img.height * ratio);
                    const ctx = canvas.getContext("2d");
                    ctx.fillStyle = "#ffffff";
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    resolve(canvas.toDataURL("image/jpeg", 0.9));
                };
                img.src = reader.result;
            };
            reader.readAsDataURL(file);
        });
    }
}

registry.category("actions").add("business_card_scan.scan", BusinessCardScanAction);
