const SERVICE_UUID = "0000ffd0-0000-1000-8000-00805f9b34fb";
const WRITE_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb";
const NOTIFY_UUID = "0000ffd2-0000-1000-8000-00805f9b34fb";

const POWER_OFF = packet([0xff, 0x00]);
const POWER_ON = packet([0xff, 0x01]);
const RESET = packet([0x00, 0x15]);
const STATIC_ENABLE = packet([0x00, 0x11, 0xf1]);
const STATIC_DISABLE = packet([0x00, 0x11, 0xf2]);
const TEMP_ENABLE = packet([0x0f, 0xf1, 0x08]);
const TEMP_DISABLE = packet([0x0f, 0xf2, 0x08]);
const START_SLIDESHOW = packet([0x00, 0x12]);
const SLIDESHOW_MARKER = packet([0x02, 0x07, 0x3c]);

const state = {
  device: null,
  writeCharacteristic: null,
  notifyCharacteristic: null,
  images: [],
  timer: null,
  config: null,
  imageIndex: 0,
  trace: [],
};

const els = {
  connect: document.querySelector("#connect"),
  disconnect: document.querySelector("#disconnect"),
  status: document.querySelector("#device-status"),
  modeStatus: document.querySelector("#mode-status"),
  mode: document.querySelector("#mode"),
  seconds: document.querySelector("#seconds"),
  image: document.querySelector("#image"),
  clockStyle: document.querySelector("#clock-style"),
  clock24h: document.querySelector("#clock-24h"),
  sendNow: document.querySelector("#send-now"),
  start: document.querySelector("#start"),
  stop: document.querySelector("#stop"),
  powerOff: document.querySelector("#power-off"),
  powerOn: document.querySelector("#power-on"),
  copyTrace: document.querySelector("#copy-trace"),
  preview: document.querySelector("#preview"),
  log: document.querySelector("#log"),
};

function log(message) {
  els.log.textContent += `${new Date().toLocaleTimeString()} ${message}\n`;
  els.log.scrollTop = els.log.scrollHeight;
}

function hex(bytes) {
  return Array.from(bytes).map((value) => value.toString(16).padStart(2, "0")).join(" ");
}

function checksum(bytes) {
  return bytes.reduce((sum, value) => (sum + value) & 0xff, 0);
}

function packet(body) {
  const bytes = [0xbc, ...body, checksum(body)];
  if ((body.length + 13) % 32 !== 0) bytes.push(0x55);
  return Uint8Array.from(bytes);
}

function gammaCorrect(value, gamma) {
  return Math.max(0, Math.min(255, Math.round(Math.pow(value / 255, 1 / gamma) * 255)));
}

function imageWrites(imageData, gamma, save) {
  const writes = [];
  if (save) {
    writes.push({ payload: RESET, delayAfterMs: 500 });
    writes.push({ payload: STATIC_ENABLE, delayAfterMs: 50 });
  }
  writes.push({ payload: TEMP_ENABLE, delayAfterMs: 50 });
  for (let chunk = 0; chunk < 8; chunk += 1) {
    const body = [0x0f, chunk + 1];
    for (let pixel = chunk * 32; pixel < (chunk + 1) * 32; pixel += 1) {
      const offset = pixel * 4;
      body.push(
        gammaCorrect(imageData.data[offset], gamma),
        gammaCorrect(imageData.data[offset + 1], gamma),
        gammaCorrect(imageData.data[offset + 2], gamma),
      );
    }
    writes.push({ payload: packet(body), delayAfterMs: 50 });
  }
  writes.push({ payload: TEMP_DISABLE, delayAfterMs: 50 });
  if (save) writes.push({ payload: STATIC_DISABLE, delayAfterMs: 50 });
  return writes;
}

function slideshowFrameWrites(imageData, imageIndex, frameCount, gamma, save) {
  const writes = [{ payload: packet([0x02, 0xf1, frameCount]), delayAfterMs: 5 }];
  for (let chunk = 0; chunk < 8; chunk += 1) {
    const body = [0x02, imageIndex, chunk + 1];
    for (let pixel = chunk * 32; pixel < (chunk + 1) * 32; pixel += 1) {
      const offset = pixel * 4;
      body.push(
        gammaCorrect(imageData.data[offset], gamma),
        gammaCorrect(imageData.data[offset + 1], gamma),
        gammaCorrect(imageData.data[offset + 2], gamma),
      );
    }
    writes.push({ payload: packet(body), delayAfterMs: 5 });
  }
  if (save && imageIndex === frameCount) {
    writes.push({ payload: SLIDESHOW_MARKER, delayAfterMs: 5 });
  }
  writes.push({ payload: packet([0x02, 0xf2, frameCount]), delayAfterMs: 5 });
  return writes;
}

async function sendSlideshow(urls) {
  const frameCount = Math.min(urls.length, 8);
  const writes = [];
  if (state.config.device.save) {
    writes.push({ payload: RESET, delayAfterMs: 500 });
    writes.push({ payload: STATIC_ENABLE, delayAfterMs: 50 });
  }
  writes.push({ payload: START_SLIDESHOW, delayAfterMs: 500 });
  for (let index = 0; index < frameCount; index += 1) {
    const data = await loadImageToCanvas(urls[index]);
    writes.push(...slideshowFrameWrites(data, index + 1, frameCount, state.config.device.gamma, state.config.device.save));
    writes.push({ payload: null, delayAfterMs: 50 });
  }
  if (state.config.device.save) {
    writes.push({ payload: STATIC_DISABLE, delayAfterMs: 50 });
  }
  writes.push({ payload: START_SLIDESHOW, delayAfterMs: 50 });
  await sendWrites(writes);
}

async function loadImageToCanvas(url) {
  const image = new Image();
  const cacheBusted = new URL(url, window.location.origin);
  cacheBusted.searchParams.set("t", Date.now());
  image.src = cacheBusted.toString();
  await image.decode();
  const ctx = els.preview.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, 16, 16);
  ctx.drawImage(image, 0, 0, 16, 16);
  return ctx.getImageData(0, 0, 16, 16);
}

async function sendWrites(writes) {
  if (!state.writeCharacteristic) throw new Error("Display is not connected");
  const startedAt = performance.now();
  state.trace = [];
  for (const { payload, delayAfterMs } of writes) {
    if (payload) {
      await state.writeCharacteristic.writeValueWithoutResponse(payload);
      const elapsedMs = Math.round(performance.now() - startedAt);
      const entry = `${String(elapsedMs).padStart(4, " ")} ms  ${hex(payload)}`;
      state.trace.push(entry);
      console.log(entry);
    }
    await sleep(delayAfterMs);
  }
}

async function sendSelectedImage() {
  const selected = state.images.find((item) => item.name === els.image.value);
  if (!selected) return;
  if (selected.name.toLowerCase().endsWith(".gif")) {
    const animation = await fetch(`/api/animation/${encodeURI(selected.name)}`).then((response) => response.json());
    if (animation.animated) {
      await sendSlideshow(animation.urls);
      log(`sent animated image ${selected.name} (${animation.frames} frames)`);
      return;
    }
  }
  const data = await loadImageToCanvas(selected.url);
  await sendWrites(imageWrites(data, state.config.device.gamma, state.config.device.save));
  log(`sent image ${selected.name}`);
}

async function sendClock() {
  const params = new URLSearchParams({
    style: els.clockStyle.value,
    clock_24h: String(els.clock24h.checked),
  });
  const data = await loadImageToCanvas(`/api/clock.png?${params.toString()}`);
  await sendWrites(imageWrites(data, state.config.device.gamma, state.config.device.save));
  log(`sent ${els.clockStyle.value} clock`);
}

async function sendCurrentMode() {
  if (els.mode.value === "clock") {
    await sendClock();
    return;
  }
  await sendSelectedImage();
}

function stopLoop() {
  if (state.timer) window.clearInterval(state.timer);
  state.timer = null;
  els.modeStatus.textContent = "Stopped";
}

function startLoop() {
  stopLoop();
  const seconds = Math.max(5, Number(els.seconds.value) || 300);
  if (els.mode.value === "carousel") {
    state.timer = window.setInterval(async () => {
      state.imageIndex = (state.imageIndex + 1) % state.images.length;
      els.image.value = state.images[state.imageIndex].name;
      await sendSelectedImage();
    }, seconds * 1000);
  } else if (els.mode.value === "clock") {
    state.timer = window.setInterval(sendClock, 60 * 1000);
  } else {
    state.timer = window.setInterval(sendSelectedImage, seconds * 1000);
  }
  els.modeStatus.textContent = `Running ${els.mode.value}`;
}

async function connect() {
  state.device = await navigator.bluetooth.requestDevice({
    filters: [{ name: state.config.device.name }],
    optionalServices: [SERVICE_UUID],
  });
  state.device.addEventListener("gattserverdisconnected", disconnect);
  const server = await state.device.gatt.connect();
  const service = await server.getPrimaryService(SERVICE_UUID);
  state.writeCharacteristic = await service.getCharacteristic(WRITE_UUID);
  state.notifyCharacteristic = await service.getCharacteristic(NOTIFY_UUID);
  await state.notifyCharacteristic.startNotifications();
  els.status.textContent = `Connected: ${state.device.name}`;
  setConnected(true);
  log(`connected to ${state.device.name}`);
}

function disconnect() {
  stopLoop();
  if (state.device?.gatt?.connected) state.device.gatt.disconnect();
  state.device = null;
  state.writeCharacteristic = null;
  state.notifyCharacteristic = null;
  els.status.textContent = "Not connected";
  setConnected(false);
  log("disconnected");
}

function setConnected(connected) {
  els.connect.disabled = connected;
  els.disconnect.disabled = !connected;
  els.sendNow.disabled = !connected;
  els.start.disabled = !connected;
  els.stop.disabled = !connected;
  els.powerOff.disabled = !connected;
  els.powerOn.disabled = !connected;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function boot() {
  state.config = await fetch("/api/config").then((response) => response.json());
  state.images = await fetch("/api/images").then((response) => response.json());
  els.mode.value = state.config.mode.type;
  els.seconds.value = state.config.mode.carousel_seconds;
  els.clockStyle.value = state.config.mode.clock_style;
  els.clock24h.checked = state.config.mode.clock_24h;
  for (const image of state.images) {
    const option = document.createElement("option");
    option.value = image.name;
    option.textContent = image.name;
    els.image.append(option);
  }
  if (state.images.length) {
    const desired = state.config.mode.single_image.replace(/^images\//, "");
    els.image.value = state.images.some((image) => image.name === desired) ? desired : state.images[0].name;
    await loadImageToCanvas(state.images[0].url);
  }
}

els.connect.addEventListener("click", () => connect().catch((error) => log(error.message)));
els.disconnect.addEventListener("click", disconnect);
els.sendNow.addEventListener("click", () => sendCurrentMode().catch((error) => log(error.message)));
els.start.addEventListener("click", () => {
  startLoop();
  sendCurrentMode().catch((error) => log(error.message));
});
els.stop.addEventListener("click", stopLoop);
els.powerOff.addEventListener("click", () => sendWrites([{ payload: POWER_OFF, delayAfterMs: 50 }]).then(() => log("power off sent")));
els.powerOn.addEventListener("click", () => sendWrites([{ payload: POWER_ON, delayAfterMs: 50 }]).then(() => log("power on sent")));
els.copyTrace.addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.trace.join("\n"));
  log(`copied ${state.trace.length} trace lines`);
});
els.image.addEventListener("change", () => {
  const selected = state.images.find((item) => item.name === els.image.value);
  if (selected) loadImageToCanvas(selected.url);
});

boot().catch((error) => log(error.message));
