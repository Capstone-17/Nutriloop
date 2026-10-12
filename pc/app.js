/**
 * Nutriloop - Royal Clinical Desktop Frontend Engine
 * Primary: Maroon Reddish | Secondary: Golden Yellow
 * Full Slider-Driven Real-Time Health Monitor Logic
 */

// Global State
let appBridgeInitialized = false;
let currentWeeklyPlan = null;
let chatHistory = [];
let downloadPollTimer = null;
let currentAssessmentData = null;
let activeExplainDisease = "ckd";
let activeSelectedTest = { is_latest: true, date: null, id: null };
let modalTargetField = null;
let confirmCallback = null;

// Curated 45+ Alliterative Fun Animal Titles
const ALLITERATIVE_NAMES = [
  "Sorcerer Swan", "Beauty Bee", "Clever Cheetah", "Daring Dolphin",
  "Fearless Falcon", "Gentle Giraffe", "Heroic Hawk", "Jolly Jaguar",
  "Kind Koala", "Luminous Lynx", "Mighty Monkey", "Noble Narwhal",
  "Peppy Penguin", "Quick Quail", "Radiant Raven", "Stellar Starling",
  "Valiant Viper", "Wise Walrus", "Mystic Moose", "Astral Alpaca",
  "Brave Bear", "Cosmic Crane", "Dynamic Deer", "Epic Eagle",
  "Gallant Gecko", "Harmonious Hummingbird", "Infinite Iguana", "Jovial Jackal",
  "Keen Kingfisher", "Loyal Leopard", "Majestic Mustang", "Nimble Newt",
  "Optimistic Otter", "Peaceful Panda", "Quantum Quokka", "Royal Rhino",
  "Serene Seal", "Thunder Tiger", "Unique Unicorn", "Victorious Vulture",
  "Witty Wolf", "Xenon X-Ray Tetra", "Youthful Yak", "Zen Zebra"
];

function getRandomAlliterativeName() {
  const idx = Math.floor(Math.random() * ALLITERATIVE_NAMES.length);
  return ALLITERATIVE_NAMES[idx];
}

/**
 * Format decimal capped at maxPlaces (default 2), eliminating float artifacts and trimming trailing zeroes.
 */
function formatDecimal(val, maxPlaces = 2) {
  if (val === null || val === undefined || isNaN(Number(val))) return "0";
  const num = Number(val);
  const factor = Math.pow(10, maxPlaces);
  const rounded = Math.round((num + Number.EPSILON) * factor) / factor;
  return rounded.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxPlaces,
    useGrouping: false,
  });
}

// Immediate instantaneous UI setup on DOM load (0ms latency!)
window.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupEventListeners();
  applySafeClinicalDefaults();
  updateHealthGaugesFromInputs();

  setTimeout(() => {
    if (window.pywebview && window.pywebview.api && !appBridgeInitialized) {
      appBridgeInitialized = true;
      initApp();
    }
  }, 200);
});

// Wait for pywebview bridge readiness
window.addEventListener("pywebviewready", () => {
  console.log("Nutriloop Desktop Bridge Ready");
  if (!appBridgeInitialized) {
    appBridgeInitialized = true;
    initApp();
  }
});

async function initApp() {
  // 1. Immediately load initial patient test in background (updates sliders if previous report exists)
  try {
    await checkAndLoadInitialPatient();
  } catch (err) {
    console.warn("Initial patient load:", err);
  }

  // 2. Load system info, ollama status, reports, and AI settings asynchronously in parallel (non-blocking)
  Promise.allSettled([
    loadSystemInfo(),
    refreshOllamaStatus(),
    refreshSavedReports(),
    loadAiSettings()
  ]).catch((err) => console.warn("Background system initialization error:", err));
}

/* ──────────────────────────────────────────────────────────────────────────
   Navigation & Tabs
   ────────────────────────────────────────────────────────────────────────── */

function setupTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      const targetId = tab.getAttribute("data-tab");
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("active");
      });
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });
}

function switchTab(tabId) {
  const tabBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  if (tabBtn) tabBtn.click();
}

/* ──────────────────────────────────────────────────────────────────────────
   System Info & Patient Test History
   ────────────────────────────────────────────────────────────────────────── */

async function loadSystemInfo() {
  if (!window.pywebview?.api) return;
  try {
    const info = await window.pywebview.api.get_system_info();
    const dataDir = info.user_data_dir || "./";
    if (document.getElementById("settings-data-dir")) {
      document.getElementById("settings-data-dir").value = dataDir;
    }
    if (document.getElementById("settings-db-path")) {
      document.getElementById("settings-db-path").value = info.db_path || "app_data.db";
    }
  } catch (err) {
    console.error("Failed to load system info:", err);
  }
}

function applySafeClinicalDefaults() {
  const userEl = document.getElementById("p-user-id");
  if (userEl && (!userEl.value || userEl.value === "John Doe")) {
    userEl.value = getRandomAlliterativeName();
  }
  if (document.getElementById("p-age")) document.getElementById("p-age").value = 45;
  setSexValue("male");
  if (document.getElementById("p-bmi")) document.getElementById("p-bmi").value = 22.0;

  if (document.getElementById("p-sbp")) document.getElementById("p-sbp").value = 115;
  if (document.getElementById("p-dbp")) document.getElementById("p-dbp").value = 75;
  if (document.getElementById("p-fbg")) document.getElementById("p-fbg").value = 90;
  if (document.getElementById("p-hba1c")) document.getElementById("p-hba1c").value = 5.2;
  if (document.getElementById("p-creat")) document.getElementById("p-creat").value = 0.9;
  if (document.getElementById("p-egfr")) document.getElementById("p-egfr").value = 100.0;
  if (document.getElementById("p-pot")) document.getElementById("p-pot").value = 4.2;
  if (document.getElementById("p-sod")) document.getElementById("p-sod").value = 140;
  const sumEl = document.getElementById("p-summary");
  if (sumEl) sumEl.value = "";

  activeSelectedTest = { is_latest: true, date: null, id: null };
  updateDietHistoricalWarning();
  updateHealthGaugesFromInputs();
}

async function populatePatientTestHistory(userId = null, selectTestId = null) {
  if (!window.pywebview?.api) return;
  try {
    const currentId = userId || document.getElementById("p-user-id")?.value || "";
    const historyList = await window.pywebview.api.list_patient_tests(currentId);
    const selector = document.getElementById("preset-selector");
    const deleteBtn = document.getElementById("btn-delete-test");
    if (!selector) return;
    selector.innerHTML = "";

    if (!historyList || historyList.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "-- No Previous Test Reports --";
      selector.appendChild(opt);
      if (deleteBtn) deleteBtn.style.display = "none";
      return;
    }

    if (deleteBtn) deleteBtn.style.display = "inline-block";

    historyList.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.label;
      selector.appendChild(opt);
    });

    if (selectTestId) {
      selector.value = String(selectTestId);
    } else {
      selector.selectedIndex = 0;
    }
  } catch (err) {
    console.error("Failed to list patient test history:", err);
  }
}

async function checkAndLoadInitialPatient() {
  if (!window.pywebview?.api) return;
  try {
    const currentId = document.getElementById("p-user-id")?.value || "";
    const res = await window.pywebview.api.get_latest_test(currentId);
    if (res && res.found) {
      populateFormWithPatient(res);
      await populatePatientTestHistory(res.user_id, res.id);
      if (res.assessments && Object.keys(res.assessments).length > 0) {
        currentAssessmentData = res.assessments;
        renderAssessmentResults({ assessments: res.assessments, detected_conditions: res.detected_conditions });
        selectExplainDisease(activeExplainDisease);
        const badge = document.getElementById("assessment-status-badge");
        if (badge) badge.style.display = "inline-block";
      }
      activeSelectedTest = { is_latest: true, date: res.created_at, id: res.id };
    } else {
      applySafeClinicalDefaults();
      await populatePatientTestHistory(document.getElementById("p-user-id")?.value);
    }
    updateDietHistoricalWarning();
  } catch (err) {
    console.error("Failed to load initial patient test:", err);
    applySafeClinicalDefaults();
  }
}

function updateDietHistoricalWarning() {
  const warnBox = document.getElementById("diet-historical-warning");
  const dateSpan = document.getElementById("diet-warning-date");
  if (!warnBox) return;

  if (!activeSelectedTest.is_latest && activeSelectedTest.date) {
    warnBox.style.display = "block";
    if (dateSpan) {
      dateSpan.textContent = activeSelectedTest.date.replace("T", " ").slice(0, 16);
    }
  } else {
    warnBox.style.display = "none";
  }
}

function populateFormWithPatient(p) {
  if (p.user_id) document.getElementById("p-user-id").value = p.user_id;
  if (p.age_years != null && document.getElementById("p-age")) document.getElementById("p-age").value = p.age_years;
  if (p.sex && document.getElementById("p-sex")) {
    setSexValue(p.sex.toLowerCase());
  }
  if (p.body_mass_index != null && document.getElementById("p-bmi")) document.getElementById("p-bmi").value = p.body_mass_index;

  const labs = p.test_reports || p.raw_inputs || p;
  if (labs.systolic_bp_mmhg != null && document.getElementById("p-sbp")) document.getElementById("p-sbp").value = labs.systolic_bp_mmhg;
  if (labs.diastolic_bp_mmhg != null && document.getElementById("p-dbp")) document.getElementById("p-dbp").value = labs.diastolic_bp_mmhg;
  if (labs.fasting_glucose_mg_dl != null && document.getElementById("p-fbg")) document.getElementById("p-fbg").value = labs.fasting_glucose_mg_dl;
  if (labs.hba1c_pct != null && document.getElementById("p-hba1c")) document.getElementById("p-hba1c").value = labs.hba1c_pct;
  if (labs.serum_creatinine_mg_dl != null && document.getElementById("p-creat")) document.getElementById("p-creat").value = labs.serum_creatinine_mg_dl;
  if (labs.egfr_ml_min != null && document.getElementById("p-egfr")) document.getElementById("p-egfr").value = labs.egfr_ml_min;
  if (labs.serum_potassium_meq_l != null && document.getElementById("p-pot")) document.getElementById("p-pot").value = labs.serum_potassium_meq_l;
  if (labs.serum_sodium_meq_l != null && document.getElementById("p-sod")) document.getElementById("p-sod").value = labs.serum_sodium_meq_l;
  const sumEl = document.getElementById("p-summary");
  if (sumEl && labs.report_summary_text != null) sumEl.value = labs.report_summary_text;
  updateHealthGaugesFromInputs();
}

/* ──────────────────────────────────────────────────────────────────────────
   Sex Toggle Handler
   ────────────────────────────────────────────────────────────────────────── */

function setSexValue(sex) {
  const hiddenSex = document.getElementById("p-sex");
  if (hiddenSex) hiddenSex.value = sex;

  const btnMale = document.getElementById("btn-sex-male");
  const btnFemale = document.getElementById("btn-sex-female");
  if (btnMale) btnMale.classList.toggle("active", sex === "male");
  if (btnFemale) btnFemale.classList.toggle("active", sex === "female");

  const valEl = document.getElementById("gauge-sex-val");
  const badgeEl = document.getElementById("gauge-sex-badge");
  if (valEl) valEl.textContent = sex === "female" ? "Female" : "Male";
  if (badgeEl) badgeEl.textContent = sex === "female" ? "Female Baseline" : "Male Baseline";

  updateHealthGaugesFromInputs();
}
window.setSexValue = setSexValue;

/* ──────────────────────────────────────────────────────────────────────────
   Real-Time Health Gauges & Active Patient Synchronization
   ────────────────────────────────────────────────────────────────────────── */

function updateHealthGaugesFromInputs() {
  const age = parseFloat(document.getElementById("p-age")?.value) || 45;
  const bmi = parseFloat(document.getElementById("p-bmi")?.value) || 22.0;
  const sbp = parseFloat(document.getElementById("p-sbp")?.value) || 115;
  const dbp = parseFloat(document.getElementById("p-dbp")?.value) || 75;
  const fbg = parseFloat(document.getElementById("p-fbg")?.value) || 90;
  const hba1c = parseFloat(document.getElementById("p-hba1c")?.value) || 5.2;
  const creat = parseFloat(document.getElementById("p-creat")?.value) || 0.9;
  const egfr = parseFloat(document.getElementById("p-egfr")?.value) || 100;
  const pot = parseFloat(document.getElementById("p-pot")?.value) || 4.2;
  const sod = parseFloat(document.getElementById("p-sod")?.value) || 140;

  // 1. Sidebar Patient Name & Initials
  let userEl = document.getElementById("p-user-id");
  let userId = userEl?.value?.trim();
  if (!userId) {
    userId = getRandomAlliterativeName();
    if (userEl) userEl.value = userId;
  }
  const avatarEl = document.getElementById("sidebar-patient-avatar");
  if (avatarEl) {
    avatarEl.title = `Patient: ${userId}`;
    if (!avatarEl.querySelector("img")) {
      avatarEl.innerHTML = '<img src="../assets/Nutriloop_1.png" alt="NutriLoop Logo" class="patient-avatar-logo">';
    }
  }

  // 2. Sync Regional Cuisine select and hidden input
  const cuisineEl = document.getElementById("diet-cuisine");
  const regionHidden = document.getElementById("diet-region");
  if (cuisineEl && regionHidden) {
    regionHidden.value = cuisineEl.value;
  }

  const C = 301.6; // 2 * Math.PI * 48

  const setGauge = (strokeId, valId, badgeId, rawValText, min, max, val, statusText, statusClass, strokeColorClass) => {
    const strokeEl = document.getElementById(strokeId);
    const valEl = document.getElementById(valId);
    const badgeEl = document.getElementById(badgeId);

    if (valEl) valEl.textContent = rawValText;
    if (strokeEl) {
      const pct = Math.max(3, Math.min(100, ((val - min) / (max - min)) * 100));
      const offset = C - (pct / 100) * C;
      strokeEl.style.strokeDashoffset = `${offset}`;
      strokeEl.className.baseVal = `gauge-stroke ${strokeColorClass}`;
    }
    if (badgeEl) {
      badgeEl.textContent = statusText;
      badgeEl.className = `gauge-status-badge ${statusClass}`;
    }
  };

  // 1. Age (18 - 100)
  const ageStatus = age < 45 ? "Young Adult" : age < 65 ? "Mature Adult" : "Senior Adult";
  setGauge("gauge-age-stroke", "gauge-age-val", "gauge-age-badge", Math.round(age), 18, 100, age, ageStatus, "badge-normal", "stroke-gold");

  // 2. BMI (10.0 - 60.0)
  let bmiStatus = "Normal";
  let bmiClass = "badge-normal";
  let bmiStroke = "stroke-emerald";
  if (bmi >= 30.0) {
    bmiStatus = "Obesity";
    bmiClass = "badge-danger";
    bmiStroke = "stroke-maroon";
  } else if (bmi >= 25.0) {
    bmiStatus = "Overweight";
    bmiClass = "badge-warning";
    bmiStroke = "stroke-amber";
  } else if (bmi < 18.5) {
    bmiStatus = "Underweight";
    bmiClass = "badge-warning";
    bmiStroke = "stroke-amber";
  }
  setGauge("gauge-bmi-stroke", "gauge-bmi-val", "gauge-bmi-badge", formatDecimal(bmi, 2), 10.0, 60.0, bmi, bmiStatus, bmiClass, bmiStroke);

  // 3. Systolic BP (70 - 240)
  let sbpStatus = "Optimal";
  let sbpClass = "badge-normal";
  let sbpStroke = "stroke-emerald";
  if (sbp >= 140) {
    sbpStatus = "Stage 2 HTN";
    sbpClass = "badge-danger";
    sbpStroke = "stroke-rose";
  } else if (sbp >= 130) {
    sbpStatus = "Stage 1 HTN";
    sbpClass = "badge-danger";
    sbpStroke = "stroke-maroon";
  } else if (sbp >= 120) {
    sbpStatus = "Elevated";
    sbpClass = "badge-warning";
    sbpStroke = "stroke-amber";
  }
  setGauge("gauge-sbp-stroke", "gauge-sbp-val", "gauge-sbp-badge", Math.round(sbp), 70, 240, sbp, sbpStatus, sbpClass, sbpStroke);

  // 4. Diastolic BP (40 - 140)
  let dbpStatus = "Optimal";
  let dbpClass = "badge-normal";
  let dbpStroke = "stroke-emerald";
  if (dbp >= 90) {
    dbpStatus = "Stage 2 HTN";
    dbpClass = "badge-danger";
    dbpStroke = "stroke-rose";
  } else if (dbp >= 80) {
    dbpStatus = "Stage 1 HTN";
    dbpClass = "badge-danger";
    dbpStroke = "stroke-maroon";
  } else if (dbp >= 80) {
    dbpStatus = "Borderline";
    dbpClass = "badge-warning";
    dbpStroke = "stroke-amber";
  }
  setGauge("gauge-dbp-stroke", "gauge-dbp-val", "gauge-dbp-badge", Math.round(dbp), 40, 140, dbp, dbpStatus, dbpClass, dbpStroke);

  // 5. Fasting Glucose (50 - 350)
  let fbgStatus = "Normal";
  let fbgClass = "badge-normal";
  let fbgStroke = "stroke-emerald";
  if (fbg >= 126) {
    fbgStatus = "Elevated";
    fbgClass = "badge-danger";
    fbgStroke = "stroke-maroon";
  } else if (fbg >= 100) {
    fbgStatus = "Prediabetes";
    fbgClass = "badge-warning";
    fbgStroke = "stroke-amber";
  } else if (fbg < 70) {
    fbgStatus = "Low Glucose";
    fbgClass = "badge-warning";
    fbgStroke = "stroke-amber";
  }
  setGauge("gauge-fbg-stroke", "gauge-fbg-val", "gauge-fbg-badge", Math.round(fbg), 50, 350, fbg, fbgStatus, fbgClass, fbgStroke);

  // 6. HbA1c (3.5 - 16.0)
  let hba1cStatus = "Normal";
  let hba1cClass = "badge-normal";
  let hba1cStroke = "stroke-emerald";
  if (hba1c >= 6.5) {
    hba1cStatus = "Diabetic";
    hba1cClass = "badge-danger";
    hba1cStroke = "stroke-maroon";
  } else if (hba1c >= 5.7) {
    hba1cStatus = "Prediabetes";
    hba1cClass = "badge-warning";
    hba1cStroke = "stroke-amber";
  }
  setGauge("gauge-hba1c-stroke", "gauge-hba1c-val", "gauge-hba1c-badge", formatDecimal(hba1c, 2), 3.5, 16.0, hba1c, hba1cStatus, hba1cClass, hba1cStroke);

  // 7. Serum Creatinine (0.2 - 10.0)
  let creatStatus = "Normal";
  let creatClass = "badge-normal";
  let creatStroke = "stroke-emerald";
  if (creat > 1.5) {
    creatStatus = "Elevated";
    creatClass = "badge-danger";
    creatStroke = "stroke-maroon";
  } else if (creat > 1.2) {
    creatStatus = "Borderline";
    creatClass = "badge-warning";
    creatStroke = "stroke-amber";
  }
  setGauge("gauge-creat-stroke", "gauge-creat-val", "gauge-creat-badge", formatDecimal(creat, 2), 0.2, 10.0, creat, creatStatus, creatClass, creatStroke);

  // 8. eGFR (5 - 140)
  let egfrStatus = "Optimal";
  let egfrClass = "badge-normal";
  let egfrStroke = "stroke-gold";
  if (egfr < 30) {
    egfrStatus = "Severe CKD";
    egfrClass = "badge-danger";
    egfrStroke = "stroke-rose";
  } else if (egfr < 60) {
    egfrStatus = "Moderate CKD";
    egfrClass = "badge-danger";
    egfrStroke = "stroke-maroon";
  } else if (egfr < 90) {
    egfrStatus = "Mild Reduct.";
    egfrClass = "badge-warning";
    egfrStroke = "stroke-amber";
  }
  setGauge("gauge-egfr-stroke", "gauge-egfr-val", "gauge-egfr-badge", formatDecimal(egfr, 2), 5, 140, egfr, egfrStatus, egfrClass, egfrStroke);

  // 9. Serum Potassium (2.5 - 7.5)
  let potStatus = "Normal";
  let potClass = "badge-normal";
  let potStroke = "stroke-emerald";
  if (pot > 5.5) {
    potStatus = "Hyperkalemia";
    potClass = "badge-danger";
    potStroke = "stroke-maroon";
  } else if (pot > 5.0) {
    potStatus = "Mild High";
    potClass = "badge-warning";
    potStroke = "stroke-amber";
  } else if (pot < 3.5) {
    potStatus = "Hypokalemia";
    potClass = "badge-warning";
    potStroke = "stroke-amber";
  }
  setGauge("gauge-pot-stroke", "gauge-pot-val", "gauge-pot-badge", formatDecimal(pot, 2), 2.5, 7.5, pot, potStatus, potClass, potStroke);

  // 10. Serum Sodium (110 - 170)
  let sodStatus = "Normal";
  let sodClass = "badge-normal";
  let sodStroke = "stroke-emerald";
  if (sod > 145) {
    sodStatus = "Elevated";
    sodClass = "badge-danger";
    sodStroke = "stroke-maroon";
  } else if (sod < 135) {
    sodStatus = "Low Sodium";
    sodClass = "badge-warning";
    sodStroke = "stroke-amber";
  }
  setGauge("gauge-sod-stroke", "gauge-sod-val", "gauge-sod-badge", Math.round(sod), 110, 170, sod, sodStatus, sodClass, sodStroke);
}

/* ──────────────────────────────────────────────────────────────────────────
   Custom Confirmation Modal Card
   ────────────────────────────────────────────────────────────────────────── */

function showConfirmModal({ title, message, confirmText = "Delete Report", isDanger = true, onConfirm }) {
  const modal = document.getElementById("confirm-modal");
  const titleEl = document.getElementById("confirm-modal-title");
  const msgEl = document.getElementById("confirm-modal-message");
  const proceedBtn = document.getElementById("btn-confirm-proceed");

  if (!modal || !proceedBtn) {
    if (confirm(message)) {
      if (onConfirm) onConfirm();
    }
    return;
  }

  if (titleEl) titleEl.textContent = title || "Delete Test Report";
  if (msgEl) msgEl.textContent = message;
  proceedBtn.textContent = confirmText;
  proceedBtn.className = isDanger ? "btn btn-danger" : "btn btn-primary";
  confirmCallback = onConfirm;

  modal.style.display = "flex";
}

function closeConfirmModal() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.style.display = "none";
  confirmCallback = null;
}

function runDeleteActiveTest() {
  if (!window.pywebview?.api) return;
  if (!activeSelectedTest.id) {
    showClinicalModal("Please select a historical test from the dropdown to delete.");
    return;
  }

  showConfirmModal({
    title: "Delete Test Report",
    message: `Are you sure you want to permanently delete test report #${activeSelectedTest.id}? This action cannot be undone.`,
    confirmText: "Yes, Delete Report",
    isDanger: true,
    onConfirm: async () => {
      try {
        const res = await window.pywebview.api.delete_patient_test(activeSelectedTest.id);
        if (res && res.status === "success") {
          const userId = document.getElementById("p-user-id").value;
          await populatePatientTestHistory(userId);
          await checkAndLoadInitialPatient();
          showClinicalModal("Test report successfully deleted from database.");
        } else {
          showClinicalModal("Failed to delete test report.");
        }
      } catch (err) {
        showClinicalModal("Delete error: " + err);
      }
    }
  });
}

/* ──────────────────────────────────────────────────────────────────────────
   Multi-Disease Risk Assessment & Event Listeners
   ────────────────────────────────────────────────────────────────────────── */

function setupEventListeners() {
  document.getElementById("btn-assess-patient")?.addEventListener("click", runAssessment);
  document.getElementById("btn-transfer-diet")?.addEventListener("click", () => {
    switchTab("tab-diet");
  });

  document.getElementById("btn-generate-diet")?.addEventListener("click", runWeeklyDiet);
  document.getElementById("btn-save-diet")?.addEventListener("click", saveWeeklyDiet);
  document.getElementById("btn-open-folder-diet")?.addEventListener("click", openReportsFolder);
  document.getElementById("btn-open-folder")?.addEventListener("click", openReportsFolder);
  document.getElementById("btn-close-save-modal")?.addEventListener("click", closeSaveNoticeModal);
  document.getElementById("btn-dismiss-save-modal")?.addEventListener("click", closeSaveNoticeModal);
  document.getElementById("btn-open-reports-dir")?.addEventListener("click", openReportsFolder);

  document.getElementById("btn-chat-send")?.addEventListener("click", sendChatMessage);
  document.getElementById("chat-input-text")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
  document.getElementById("btn-save-ai-key")?.addEventListener("click", saveAiSettings);
  document.getElementById("ai-engine-select")?.addEventListener("change", () => {
    saveAiSettings();
  });

  document.getElementById("btn-refresh-ollama")?.addEventListener("click", refreshOllamaStatus);
  document.getElementById("btn-install-model")?.addEventListener("click", installOllamaModel);
  document.getElementById("btn-pause-model")?.addEventListener("click", pauseOllamaDownload);
  document.getElementById("btn-cancel-model")?.addEventListener("click", cancelOllamaDownload);
  document.getElementById("btn-delete-model")?.addEventListener("click", deleteOllamaModel);

  // Delete Test Button
  document.getElementById("btn-delete-test")?.addEventListener("click", runDeleteActiveTest);

  // Confirm Modal Action Handlers
  document.getElementById("btn-confirm-close")?.addEventListener("click", closeConfirmModal);
  document.getElementById("btn-confirm-cancel")?.addEventListener("click", closeConfirmModal);
  document.getElementById("btn-confirm-proceed")?.addEventListener("click", () => {
    const cb = confirmCallback;
    closeConfirmModal();
    if (cb) cb();
  });

  // User ID Change updates history dropdown for that patient and recomputes avatar
  const userEl = document.getElementById("p-user-id");
  if (userEl) {
    userEl.addEventListener("change", () => {
      populatePatientTestHistory(userEl.value || "John Doe");
      updateHealthGaugesFromInputs();
    });
    userEl.addEventListener("input", updateHealthGaugesFromInputs);
  }

  // Sex Toggle Buttons
  document.getElementById("btn-sex-male")?.addEventListener("click", () => setSexValue("male"));
  document.getElementById("btn-sex-female")?.addEventListener("click", () => setSexValue("female"));

  // Biomarker Range Sliders live input listeners
  const sliderIds = ["p-age", "p-bmi", "p-sbp", "p-dbp", "p-fbg", "p-hba1c", "p-creat", "p-egfr", "p-pot", "p-sod"];
  sliderIds.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", updateHealthGaugesFromInputs);
      el.addEventListener("change", updateHealthGaugesFromInputs);
    }
  });

  // Synchronize Regional Cuisine selector
  document.getElementById("diet-cuisine")?.addEventListener("change", () => {
    const regEl = document.getElementById("diet-region");
    if (regEl) regEl.value = document.getElementById("diet-cuisine").value;
  });

  // History Selector Change Handler
  document.getElementById("preset-selector")?.addEventListener("change", async (e) => {
    if (!e.target.value) {
      applySafeClinicalDefaults();
      return;
    }
    const testData = await window.pywebview.api.load_patient_test(e.target.value);
    if (testData && !testData.error) {
      populateFormWithPatient(testData);
      if (testData.assessments && Object.keys(testData.assessments).length > 0) {
        currentAssessmentData = testData.assessments;
        renderAssessmentResults({ assessments: testData.assessments, detected_conditions: testData.detected_conditions });
        selectExplainDisease(activeExplainDisease);
        const badge = document.getElementById("assessment-status-badge");
        if (badge) badge.style.display = "inline-block";
      }
      const isLatest = e.target.selectedIndex === 0 || e.target.options[e.target.selectedIndex].textContent.includes("(Latest)");
      activeSelectedTest = { is_latest: isLatest, date: testData.created_at, id: testData.id };
      updateDietHistoricalWarning();
    }
  });

  // Clinical Modal Close Handlers
  document.getElementById("btn-close-clinical-modal")?.addEventListener("click", closeClinicalModal);
  document.getElementById("btn-modal-correct")?.addEventListener("click", closeClinicalModal);

  // Explainability Tab Handlers
  document.getElementById("tab-btn-ckd")?.addEventListener("click", () => selectExplainDisease("ckd"));
  document.getElementById("tab-btn-hypertension")?.addEventListener("click", () => selectExplainDisease("hypertension"));
  document.getElementById("tab-btn-diabetes")?.addEventListener("click", () => selectExplainDisease("diabetes"));

  // Clickable Meter Cards to switch explanation
  document.getElementById("meter-ckd")?.addEventListener("click", () => selectExplainDisease("ckd"));
  document.getElementById("meter-hypertension")?.addEventListener("click", () => selectExplainDisease("hypertension"));
  document.getElementById("meter-diabetes")?.addEventListener("click", () => selectExplainDisease("diabetes"));
}

/* ──────────────────────────────────────────────────────────────────────────
   Clinical Validation Modal
   ────────────────────────────────────────────────────────────────────────── */

function showClinicalModal(message, targetFieldId = null) {
  const modal = document.getElementById("clinical-modal");
  const msgBox = document.getElementById("clinical-modal-message");
  if (!modal || !msgBox) {
    alert(message);
    return;
  }
  msgBox.textContent = message;
  modalTargetField = targetFieldId;
  modal.style.display = "flex";
}

function closeClinicalModal() {
  const modal = document.getElementById("clinical-modal");
  if (modal) modal.style.display = "none";
  if (modalTargetField) {
    const el = document.getElementById(modalTargetField);
    if (el) {
      el.focus();
      if (typeof el.select === "function") el.select();
    }
  }
}

/* ──────────────────────────────────────────────────────────────────────────
   Multi-Disease Risk Assessment Computation
   ────────────────────────────────────────────────────────────────────────── */

async function runAssessment() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById("btn-assess-patient");

  const age = parseFloat(document.getElementById("p-age")?.value) || 45;
  const sex = document.getElementById("p-sex")?.value || "male";
  const bmi = parseFloat(document.getElementById("p-bmi")?.value) || 22.0;
  const sbp = parseFloat(document.getElementById("p-sbp")?.value) || 115;
  const dbp = parseFloat(document.getElementById("p-dbp")?.value) || 75;
  const fbg = parseFloat(document.getElementById("p-fbg")?.value) || 90;
  const hba1c = parseFloat(document.getElementById("p-hba1c")?.value) || 5.2;
  const creat = parseFloat(document.getElementById("p-creat")?.value) || 0.9;
  const egfr = parseFloat(document.getElementById("p-egfr")?.value) || 100;
  const pot = parseFloat(document.getElementById("p-pot")?.value) || 4.2;
  const sod = parseFloat(document.getElementById("p-sod")?.value) || 140;

  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Computing Risk Diagnostics...";
  }

  const payload = {
    user_id: document.getElementById("p-user-id")?.value?.trim() || "John Doe",
    age_years: isNaN(age) ? 45 : age,
    sex: sex,
    body_mass_index: isNaN(bmi) ? 22.0 : bmi,
    test_reports: {
      systolic_bp_mmhg: isNaN(sbp) ? 115 : sbp,
      diastolic_bp_mmhg: isNaN(dbp) ? 75 : dbp,
      fasting_glucose_mg_dl: isNaN(fbg) ? 90 : fbg,
      hba1c_pct: isNaN(hba1c) ? 5.2 : hba1c,
      serum_creatinine_mg_dl: isNaN(creat) ? 0.9 : creat,
      egfr_ml_min: isNaN(egfr) ? 100 : egfr,
      serum_potassium_meq_l: isNaN(pot) ? 4.2 : pot,
      serum_sodium_meq_l: isNaN(sod) ? 140 : sod,
      report_summary_text: document.getElementById("p-summary")?.value || "",
    },
  };

  try {
    const res = await window.pywebview.api.assess_patient(payload);
    if (res.status === "success") {
      if (res.validation_notice) {
        showClinicalModal(res.validation_notice);
      }
      currentAssessmentData = res.assessments;
      renderAssessmentResults(res);
      selectExplainDisease(activeExplainDisease);
      const badge = document.getElementById("assessment-status-badge");
      if (badge) badge.style.display = "inline-block";

      if (res.saved_test_id) {
        await populatePatientTestHistory(payload.user_id, res.saved_test_id);
        activeSelectedTest = { is_latest: true, date: res.timestamp, id: res.saved_test_id };
        updateDietHistoricalWarning();
      }

      if (res.is_duplicate) {
        showClinicalModal("Risk assessment diagnostics updated.\n\nNotice: Your biomarker values match your latest saved report, so no duplicate test record was added to history.");
      }
    } else {
      showClinicalModal(res.message || "Clinical assessment could not be processed.");
    }
  } catch (err) {
    showClinicalModal("Clinical assessment could not be processed:\n" + err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "⚡ Run Multi-Disease Risk Assessment";
    }
  }
}

function renderAssessmentResults(res) {
  const ass = res.assessments;

  updateRiskMeter("ckd", ass.ckd);
  updateRiskMeter("hypertension", ass.hypertension);
  updateRiskMeter("diabetes", ass.diabetes);

  const condContainer = document.getElementById("detected-conditions-tags");
  if (condContainer) {
    condContainer.innerHTML = "";
    if (res.detected_conditions && res.detected_conditions.length > 0) {
      res.detected_conditions.forEach((c) => {
        const tag = document.createElement("span");
        tag.className = "brand-badge";
        tag.style.background = "rgba(244, 63, 94, 0.18)";
        tag.style.borderColor = "var(--accent-rose)";
        tag.style.color = "var(--accent-rose)";
        tag.textContent = "⚠️ " + c;
        condContainer.appendChild(tag);
      });
    } else {
      condContainer.innerHTML = '<span class="risk-badge badge-low">✅ No High Clinical Comorbidities Detected</span>';
    }
  }
  updateHealthGaugesFromInputs();
}

function selectExplainDisease(dis) {
  activeExplainDisease = dis;

  ["ckd", "hypertension", "diabetes"].forEach((d) => {
    const meter = document.getElementById(`meter-${d}`);
    if (meter) {
      if (d === dis) meter.classList.add("active-meter");
      else meter.classList.remove("active-meter");
    }
    const tabBtn = document.getElementById(`tab-btn-${d}`);
    if (tabBtn) {
      if (d === dis) tabBtn.classList.add("active");
      else tabBtn.classList.remove("active");
    }
  });

  renderExplainability(dis);
}

function renderExplainability(dis) {
  const container = document.getElementById("explain-card-content");
  if (!container) return;

  if (!currentAssessmentData || !currentAssessmentData[dis]) {
    container.innerHTML = `
      <div style="color: var(--text-muted); font-size: 12.5px; padding: 14px; text-align: center;">
        Awaiting patient evaluation. Run assessment to view tailored clinical explanations and actionable recommendations.
      </div>`;
    return;
  }

  const item = currentAssessmentData[dis];
  if (item.error) {
    container.innerHTML = `
      <div class="explain-section">
        <div class="explain-section-header">⚠️ Clinical Evaluation Notice</div>
        <div style="font-size: 12.5px; color: #fca5a5; line-height: 1.5;">${item.error}</div>
      </div>`;
    return;
  }

  const exp = item.explanation || {};
  const level = (item.risk_level || "low").toLowerCase();
  const pct = formatDecimal((item.risk_score || 0) * 100, 2);
  const dName = exp.disease_name || (dis === "ckd" ? "Chronic Kidney Disease" : dis === "hypertension" ? "Hypertension" : "Type 2 Diabetes");

  let whyTitle = exp.why_title;
  let actionTitle = exp.action_title;
  let whyReasons = exp.why_reasons || [];
  let actionSteps = exp.action_steps || [];

  if (!whyTitle) {
    if (level === "high") {
      whyTitle = "Why Is It High? (Primary Clinical Causes)";
      actionTitle = "What To Do (Urgent Clinical & Dietary Actions)";
    } else if (level === "moderate") {
      whyTitle = "Why Is It Moderate? (Key Contributing Factors)";
      actionTitle = "How To Reduce It (Targeted Corrective Steps)";
    } else {
      whyTitle = "What Is Working Well (Positive Health Signals)";
      actionTitle = "Steps To Preserve It (Daily Habits to Maintain Health)";
    }
  }

  if (!whyReasons || whyReasons.length === 0) {
    whyReasons = exp.risk_drivers && exp.risk_drivers.length > 0 ? exp.risk_drivers : [exp.clinical_summary || `Assessed risk score is ${pct}%.`];
  }
  if (!actionSteps || actionSteps.length === 0) {
    actionSteps = [
      "Review lab biomarker values regularly with your healthcare provider.",
      "Follow personalized nutritional guidance aligned with your daily metabolic targets."
    ];
  }

  const statusIcon = level === "high" ? "🔴" : level === "moderate" ? "🟡" : "🟢";
  const whyIcon = level === "high" ? "🔍" : level === "moderate" ? "🔍" : "⭐";
  const actionIcon = level === "high" ? "🚨" : level === "moderate" ? "📉" : "🌿";

  const whyReasonsHtml = whyReasons.map((r) => `<li>${r}</li>`).join("");
  const actionStepsHtml = actionSteps.map((s) => `<li>${s}</li>`).join("");

  container.innerHTML = `
    <div class="explain-meta-bar">
      <div class="explain-disease-title">${dName}</div>
      <span class="risk-badge badge-${level}">
        ${statusIcon} ${level.toUpperCase()} RISK (${pct}%)
      </span>
    </div>

    <div class="explain-section">
      <div class="explain-section-header">
        <span>${whyIcon} ${whyTitle}</span>
      </div>
      <ul class="explain-list">
        ${whyReasonsHtml}
      </ul>
    </div>

    <div class="explain-section">
      <div class="explain-section-header">
        <span>${actionIcon} ${actionTitle}</span>
      </div>
      <ul class="explain-list">
        ${actionStepsHtml}
      </ul>
    </div>
  `;
}

function updateRiskMeter(disease, data) {
  const card = document.getElementById(`meter-${disease}`);
  const scoreNum = document.getElementById(`score-${disease}`);
  const badge = document.getElementById(`badge-${disease}`);

  if (!card || !scoreNum || !badge) return;

  if (!data || data.error) {
    scoreNum.textContent = "ERR";
    badge.textContent = "NOTICE";
    badge.className = "risk-badge badge-high";
    return;
  }

  const scorePct = formatDecimal((data.risk_score || 0) * 100, 2);
  scoreNum.textContent = `${scorePct}%`;

  const level = (data.risk_level || "low").toLowerCase();
  card.className = `risk-meter-card ${level}${activeExplainDisease === disease ? " active-meter" : ""}`;

  badge.className = `risk-badge badge-${level}`;
  badge.textContent = level.toUpperCase();
}

/* ──────────────────────────────────────────────────────────────────────────
   7-Day Regional Weekly Diet Generation
   ────────────────────────────────────────────────────────────────────────── */

async function runWeeklyDiet() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById("btn-generate-diet");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Assembling Personalized 7-Day Plan...";
  }

  const likes = (document.getElementById("diet-likes")?.value || "").split(/[,;/+&]|\band\b/i).map((s) => s.trim()).filter(Boolean);
  const dislikesRaw = (document.getElementById("diet-dislikes")?.value || "").split(/[,;/+&]|\band\b/i).map((s) => s.trim()).filter(Boolean);
  const meds = (document.getElementById("diet-meds")?.value || "").split(/[,;/+&]|\band\b/i).map((s) => s.trim()).filter(Boolean);
  const craving = document.getElementById("diet-craving")?.value?.trim() || "";

  const cuisineEl = document.getElementById("diet-cuisine") || document.getElementById("diet-region");
  const cuisine = cuisineEl ? cuisineEl.value : "South Indian";

  const typeEl = document.getElementById("diet-type");
  const type = typeEl ? (typeEl.value || "vegetarian").replace("-", "_") : "vegetarian";

  const caloriesEl = document.getElementById("diet-calories");
  const calories = (caloriesEl && caloriesEl.value && caloriesEl.value.trim()) ? parseInt(caloriesEl.value, 10) : null;

  const payload = {
    user_id: document.getElementById("p-user-id")?.value?.trim() || "John Doe",
    age_years: parseFloat(document.getElementById("p-age")?.value) || 45,
    sex: document.getElementById("p-sex")?.value || "male",
    body_mass_index: parseFloat(document.getElementById("p-bmi")?.value) || 22.0,
    test_reports: {
      systolic_bp_mmhg: parseFloat(document.getElementById("p-sbp")?.value) || 115,
      diastolic_bp_mmhg: parseFloat(document.getElementById("p-dbp")?.value) || 75,
      fasting_glucose_mg_dl: parseFloat(document.getElementById("p-fbg")?.value) || 90,
      hba1c_pct: parseFloat(document.getElementById("p-hba1c")?.value) || 5.2,
      serum_creatinine_mg_dl: parseFloat(document.getElementById("p-creat")?.value) || 0.9,
      egfr_ml_min: parseFloat(document.getElementById("p-egfr")?.value) || 100,
      serum_potassium_meq_l: parseFloat(document.getElementById("p-pot")?.value) || 4.2,
      serum_sodium_meq_l: parseFloat(document.getElementById("p-sod")?.value) || 140,
      report_summary_text: document.getElementById("p-summary")?.value || "",
    },
    preferences: {
      native_place_region: cuisine,
      dietary_type: type,
      calorie_target_kcal: calories,
      calorie_target_override: calories,
      interests_and_likes: likes,
      allergies: dislikesRaw,
      dislikes: dislikesRaw,
      active_medications: meds,
      craving_or_treat: craving,
    },
  };

  try {
    const res = await window.pywebview.api.generate_weekly_diet(payload);
    if (res.status === "success" && res.plan) {
      currentWeeklyPlan = res.plan;
      renderWeeklyDietResults(res.plan);
    } else {
      showClinicalModal("Weekly Diet Generation Notice:\n\n" + (res.message || "Unknown error"));
    }
  } catch (err) {
    showClinicalModal("Weekly Diet Generation Failed:\n\n" + err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🥗 Generate Personalized 7-Day Regional Diet";
    }
  }
}

function renderWeeklyDietResults(plan) {
  const container = document.getElementById("weekly-plan-results");
  if (container) container.style.display = "block";
  const placeholder = document.getElementById("diet-placeholder");
  if (placeholder) placeholder.style.display = "none";
  const saveBtn = document.getElementById("btn-save-diet");
  if (saveBtn) saveBtn.disabled = false;

  // Smart Craving Strategy Box
  const cravingBox = document.getElementById("diet-craving-box");
  if (cravingBox) {
    if (plan.smart_craving_strategy && plan.smart_craving_strategy.requested_craving) {
      const cs = plan.smart_craving_strategy;
      cravingBox.style.display = "block";
      cravingBox.innerHTML = `
        <h4 style="color:#fbbf24; margin-bottom: 6px;">🎯 Smart Craving Optimization <span class="craving-badge">${cs.requested_craving}</span></h4>
        <p style="margin-bottom: 6px;"><strong>Scheduled Indulgence:</strong> ${cs.scheduled_day} (${cs.scheduled_meal}) — <em>${cs.indulgence_title}</em></p>
        <p style="font-size: 12.5px; opacity: 0.9; margin-bottom: 4px;">⚖️ <strong>Weekly Metabolic Balance:</strong> ${cs.metabolic_rebalance_note}</p>
        <p style="font-size: 12px; color: #fbbf24;">🔒 <strong>Strict Non-Treat Days:</strong> Days 1–6 are strictly optimized with zero sugar / zero indulgence to protect your metabolic targets.</p>
      `;
    } else {
      cravingBox.style.display = "none";
    }
  }

  // Medication Alerts
  const medAlertsBox = document.getElementById("diet-med-alerts");
  if (medAlertsBox) {
    const medAlerts = plan.medication_alerts || plan.active_medication_alerts || [];
    if (medAlerts.length > 0) {
      medAlertsBox.style.display = "block";
      let alertsHtml = "<h4 style='color:#fca5a5; margin-bottom:6px;'>⚠️ Critical Pharmacopeia & Medication Contraindications</h4><ul>";
      medAlerts.forEach((a) => {
        alertsHtml += `<li>${a}</li>`;
      });
      alertsHtml += "</ul>";
      medAlertsBox.innerHTML = alertsHtml;
    } else {
      medAlertsBox.style.display = "none";
    }
  }

  // Targets Row
  const targetsRow = document.getElementById("diet-targets-row");
  if (targetsRow) {
    const t = plan.clinical_targets || {};
    targetsRow.innerHTML = `
      <div class="target-badge">
        <div class="target-value">${formatDecimal(t.calories_kcal || 1800, 2)} kcal</div>
        <div class="target-label">Caloric Target</div>
      </div>
      <div class="target-badge">
        <div class="target-value">${formatDecimal(t.protein_g || 60, 2)} g</div>
        <div class="target-label">Protein Target</div>
      </div>
      <div class="target-badge">
        <div class="target-value">${formatDecimal(t.carbohydrate_g || 220, 2)} g</div>
        <div class="target-label">Carbohydrate Floor</div>
      </div>
      <div class="target-badge">
        <div class="target-value">${formatDecimal(t.fat_g || 50, 2)} g</div>
        <div class="target-label">Healthy Fats</div>
      </div>
      <div class="target-badge">
        <div class="target-value">&ge; ${formatDecimal(t.fiber_target_g || 28, 2)} g</div>
        <div class="target-label">Dietary Fiber</div>
      </div>
      <div class="target-badge">
        <div class="target-value">&le; ${formatDecimal(t.sodium_limit_mg || 1500, 2)} mg</div>
        <div class="target-label">Sodium Limit</div>
      </div>
      <div class="target-badge">
        <div class="target-value">&le; ${formatDecimal(t.potassium_guidance_mg || 2000, 2)} mg</div>
        <div class="target-label">Potassium Guidance</div>
      </div>
      <div class="target-badge">
        <div class="target-value">${formatDecimal(t.fluid_intake_ml || 2000, 2)} ml</div>
        <div class="target-label">Fluid Intake</div>
      </div>
      <div class="target-badge">
        <div class="target-value">${plan.regional_cuisine || "Regional"}</div>
        <div class="target-label">Cuisine Tradition</div>
      </div>
    `;
  }

  // Render 7 Days Column Button Navigator & Single Day Schedule View
  const dayNav = document.getElementById("diet-day-nav");
  const activeHeader = document.getElementById("diet-active-day-header");
  const activeMeals = document.getElementById("diet-active-day-meals");

  if (plan.days && plan.days.length > 0) {
    function selectDietDay(selectedIdx) {
      const day = plan.days[selectedIdx];
      if (!day) return;

      // Update active state on column buttons
      if (dayNav) {
        dayNav.querySelectorAll(".day-col-btn").forEach((btn, i) => {
          if (i === selectedIdx) {
            btn.classList.add("active");
          } else {
            btn.classList.remove("active");
          }
        });
      }

      // Update active day header banner
      if (activeHeader) {
        const tot = day.daily_total_nutrients || {};
        activeHeader.innerHTML = `
          <div class="day-active-title-wrap">
            <span class="day-num-badge">Day ${day.day_number}</span>
            <span class="day-active-title">${day.day_name} Clinically Rebalanced Regimen</span>
          </div>
          <div class="day-strip-metrics">
            <span class="day-metric-pill"><span class="metric-icon">🔥</span> <strong>${formatDecimal(tot.calories, 2)}</strong> kcal</span>
            <span class="day-metric-pill"><span class="metric-icon">🥩</span> P: <strong>${formatDecimal(tot.protein_g, 2)}</strong>g</span>
            <span class="day-metric-pill"><span class="metric-icon">🧂</span> Na: <strong>${formatDecimal(tot.sodium_mg, 2)}</strong>mg</span>
            <span class="day-metric-pill"><span class="metric-icon">⚡</span> K: <strong>${formatDecimal(tot.potassium_mg, 2)}</strong>mg</span>
          </div>
        `;
      }

      // Render active day meal intervals
      if (activeMeals) {
        activeMeals.innerHTML = renderDayIntervals(day.intervals);
      }
    }

    // Build the 7 column buttons
    if (dayNav) {
      dayNav.innerHTML = "";
      plan.days.forEach((day, idx) => {
        const tot = day.daily_total_nutrients || {};
        const isSundayTreat = idx === 6 && plan.smart_craving_strategy && plan.smart_craving_strategy.requested_craving;

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `day-col-btn ${idx === 0 ? "active" : ""}`;
        btn.innerHTML = `
          <span class="day-col-badge">Day ${day.day_number}</span>
          <span class="day-col-name">${day.day_name}</span>
          <span class="day-col-cal">${tot.calories ? formatDecimal(tot.calories, 2) + " kcal" : "-"}</span>
          ${isSundayTreat ? '<span class="day-col-treat-tag">🎯 Treat</span>' : ""}
        `;

        btn.addEventListener("click", () => {
          selectDietDay(idx);
        });

        dayNav.appendChild(btn);
      });
    }

    // Display Day 1 by default
    selectDietDay(0);
  }

  // Grocery Checklist
  const groceryContainer = document.getElementById("diet-grocery-list");
  const grocerySection = document.getElementById("diet-grocery-container");
  if (groceryContainer && grocerySection) {
    grocerySection.style.display = "block";
    if (plan.categorized_grocery_checklist && Object.keys(plan.categorized_grocery_checklist).length > 0) {
      let catHtml = `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; width: 100%;">`;
      for (const [catName, items] of Object.entries(plan.categorized_grocery_checklist)) {
        if (items && items.length > 0) {
          catHtml += `
            <div style="background: rgba(30, 15, 24, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 12px 14px;">
              <div style="font-weight: 700; color: #fbbf24; font-size: 13px; margin-bottom: 8px;">${catName}</div>
              <ul style="margin: 0; padding-left: 18px; line-height: 1.6; font-size: 12.5px; color: #f1f5f9;">
                ${items.map((it) => `<li>${it}</li>`).join("")}
              </ul>
            </div>
          `;
        }
      }
      catHtml += `</div>`;
      groceryContainer.innerHTML = catHtml;
    } else if (plan.grocery_checklist && plan.grocery_checklist.length > 0) {
      groceryContainer.innerHTML = plan.grocery_checklist.map((g) => `<span class="brand-badge" style="background: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.3); color: #fbbf24;">${g}</span>`).join(" ");
    }
  }
}

function renderDayIntervals(intervals) {
  if (!intervals) return "";
  return intervals
    .map((inv) => {
      const nut = inv.total_nutrients || {};
      const isStarred = (inv.meal_title || "").startsWith("⭐");
      const cleanTitle = (inv.meal_title || "").replace(/^⭐\s*/, "");
      const starBadge = isStarred
        ? `<span class="preferred-choice-badge" title="Selected specifically to match your food preferences">⭐ Preferred Choice</span>`
        : "";

      const itemsListHtml = (inv.items || [])
        .map(
          (it) => `
            <li class="interval-food-item">
              <span class="food-bullet">✦</span>
              <span class="food-name">${it.item_name}</span>
              <span class="food-portion">(${it.portion})</span>
            </li>`
        )
        .join("");

      return `
      <div class="interval-box ${isStarred ? 'starred-interval' : ''}">
        <!-- Top Bar: Category, Time Window & Right-Aligned Macro Chips -->
        <div class="interval-top-row">
          <div class="interval-badge-group">
            <span class="interval-name-chip">${inv.interval_name}</span>
            <span class="interval-time-chip">${inv.time_window}</span>
            ${starBadge}
          </div>
          <div class="interval-macros-strip">
            <span class="macro-pill cal"><span class="macro-icon">🔥</span> <strong>${nut.calories != null ? formatDecimal(nut.calories, 2) : "-"}</strong> kcal</span>
            <span class="macro-pill prot"><span class="macro-icon">🥩</span> P: <strong>${nut.protein_g != null ? formatDecimal(nut.protein_g, 2) : "-"}</strong>g</span>
            <span class="macro-pill sod"><span class="macro-icon">🧂</span> Na: <strong>${nut.sodium_mg != null ? formatDecimal(nut.sodium_mg, 2) : "-"}</strong>mg</span>
          </div>
        </div>

        <!-- Full-Width Dedicated Meal Title (Eliminates text overlapping) -->
        <div class="interval-dish-banner">
          <div class="interval-dish-title">${cleanTitle}</div>
        </div>

        <!-- Food Components List -->
        <ul class="interval-food-list">
          ${itemsListHtml}
        </ul>

        <!-- Clinical Rationale Callout Box -->
        <div class="interval-clinical-callout">
          <span class="clinical-icon">💡</span>
          <div class="clinical-text">
            <strong>Clinical Rationale:</strong> ${inv.clinical_justification || "Balanced glycemic and metabolic profile."}
          </div>
        </div>
      </div>
    `;
    })
    .join("");
}

async function saveWeeklyDiet() {
  if (!currentWeeklyPlan || !window.pywebview?.api) return;
  const pid = document.getElementById("p-user-id")?.value || "patient";
  try {
    const res = await window.pywebview.api.save_weekly_diet_report(currentWeeklyPlan, pid);
    if (res.status === "saved") {
      showSaveNoticeModal(res);
      refreshSavedReports();
    }
  } catch (err) {
    alert("Failed to save report: " + err);
  }
}

function showSaveNoticeModal(res) {
  const modal = document.getElementById("save-diet-modal");
  if (!modal) return;
  const htmlEl = document.getElementById("notice-html-filename");
  const jsonEl = document.getElementById("notice-json-filename");
  const pathEl = document.getElementById("notice-folder-path");
  if (htmlEl && res.filename) htmlEl.textContent = res.filename;
  if (jsonEl && res.json_path) {
    const parts = res.json_path.split(/[/\\]/);
    jsonEl.textContent = parts[parts.length - 1];
  }
  if (pathEl && res.html_path) {
    const parts = res.html_path.split(/[/\\]/);
    parts.pop();
    pathEl.textContent = parts.join("/");
  }
  modal.style.display = "flex";
}

function closeSaveNoticeModal() {
  const modal = document.getElementById("save-diet-modal");
  if (modal) modal.style.display = "none";
}

/* ──────────────────────────────────────────────────────────────────────────
   AI Chat Interface & Provider Settings
   ────────────────────────────────────────────────────────────────────────── */

async function loadAiSettings() {
  if (!window.pywebview?.api?.get_ai_settings) return;
  try {
    const s = await window.pywebview.api.get_ai_settings();
    const select = document.getElementById("ai-engine-select");
    const status = document.getElementById("ai-key-status");
    if (select && s.provider) {
      select.value = s.provider;
    }
    if (status) {
      if (s.has_gemini_key) {
        status.textContent = `✓ Gemini Key active (${s.gemini_masked})`;
      } else if (s.has_openai_key) {
        status.textContent = `✓ OpenAI Key active (${s.openai_masked})`;
      } else {
        status.textContent = "";
      }
    }
  } catch (e) {
    console.warn("Could not load AI settings:", e);
  }
}

async function saveAiSettings() {
  if (!window.pywebview?.api?.save_ai_settings) return;
  const select = document.getElementById("ai-engine-select");
  const keyInput = document.getElementById("ai-api-key-input");
  const status = document.getElementById("ai-key-status");
  const provider = select ? select.value : "auto";
  const apiKey = keyInput ? keyInput.value.trim() : "";

  try {
    const res = await window.pywebview.api.save_ai_settings(provider, apiKey || null);
    if (res && res.status === "success") {
      if (status) {
        status.textContent = apiKey ? "✓ Key saved successfully!" : "✓ Mode set to " + provider;
        setTimeout(() => {
          if (apiKey) status.textContent = `✓ Key active (${apiKey.slice(0, 4)}...${apiKey.slice(-4)})`;
        }, 2500);
      }
      if (keyInput && apiKey) keyInput.value = "";
    }
  } catch (err) {
    if (status) status.textContent = "Error saving settings: " + err;
  }
}

function renderMarkdown(rawText) {
  if (!rawText) return "";

  let safe = rawText
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/__(.*?)__/g, "<strong>$1</strong>");
  safe = safe.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
  safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
  safe = safe.replace(/^### (.*$)/gim, "<h4>$1</h4>");
  safe = safe.replace(/^## (.*$)/gim, "<h3>$1</h3>");

  const lines = safe.split("\n");
  let inList = false;
  let html = "";

  for (let line of lines) {
    const trimmed = line.trim();
    const isBullet = /^[•\-\*]\s+(.*)/.test(trimmed);
    const isNumList = /^\d+\.\s+(.*)/.test(trimmed);

    if (isBullet || isNumList) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      const itemContent = trimmed.replace(/^[•\-\*]\s+/, "").replace(/^\d+\.\s+/, "");
      html += `<li>${itemContent}</li>`;
    } else {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      if (trimmed === "") {
        html += "<br>";
      } else if (trimmed.startsWith("<h3>") || trimmed.startsWith("<h4>")) {
        html += trimmed;
      } else {
        html += `<p>${trimmed}</p>`;
      }
    }
  }
  if (inList) html += "</ul>";

  html = html.replace(/<p><\/p>/g, "").replace(/(<br>\s*){3,}/g, "<br><br>");
  return html;
}

function sendQuickPrompt(promptText) {
  switchTab("tab-chat");
  const input = document.getElementById("chat-input-text");
  if (input) input.value = promptText;
  sendChatMessage();
}
window.sendQuickPrompt = sendQuickPrompt;

async function sendChatMessage() {
  const input = document.getElementById("chat-input-text");
  const msg = input.value.trim();
  if (!msg) return;

  const btn = document.getElementById("btn-chat-send");
  if (btn) btn.disabled = true;
  input.value = "";

  appendChatBubble("user", msg);

  const userId = document.getElementById("p-user-id")?.value?.trim() || "John Doe";
  const disease = "ckd_t2dm_htn";

  const engineSelect = document.getElementById("ai-engine-select");
  const provider = engineSelect ? engineSelect.value : "auto";
  const keyInput = document.getElementById("ai-api-key-input");
  const apiKey = keyInput ? keyInput.value.trim() : null;

  try {
    const res = await window.pywebview.api.send_chat_message(
      userId,
      msg,
      disease,
      chatHistory,
      provider,
      apiKey || null
    );
    chatHistory.push({ role: "user", content: msg });
    chatHistory.push({ role: "assistant", content: res.reply });

    appendChatBubble("assistant", res.reply, res.engine_mode, res.escalated);

    if (res.updated_diet_plan) {
      currentWeeklyPlan = res.updated_diet_plan;
      renderWeeklyDietResults(res.updated_diet_plan);
    }
  } catch (err) {
    appendChatBubble("assistant", "Chat service error: " + err, "Error", false);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function appendChatBubble(role, text, engineMode, isEscalated = false) {
  const container = document.getElementById("chat-history") || document.getElementById("chat-messages-container");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-msg ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `chat-avatar ${role === "assistant" ? "bot-avatar" : "user-avatar"}`;
  if (role === "assistant") {
    const img = document.createElement("img");
    img.src = "../assets/Nutriloop_2.png";
    img.alt = "Dr. Nutriloop";
    img.className = "bot-avatar-img";
    avatar.appendChild(img);
  } else {
    avatar.textContent = "👤";
  }

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";

  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(text);
    if (isEscalated) {
      const alertTag = document.createElement("div");
      alertTag.style.fontSize = "11px";
      alertTag.style.color = "#ff6b6b";
      alertTag.style.marginTop = "8px";
      alertTag.style.fontWeight = "700";
      alertTag.textContent = "🚨 Medical Emergency Warning";
      bubble.appendChild(alertTag);
    }
  } else {
    bubble.textContent = text;
  }

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  container.appendChild(msgDiv);

  const scrollArea = container.closest(".chat-messages-scroll-area") || container;
  scrollArea.scrollTop = scrollArea.scrollHeight;
  container.scrollTop = container.scrollHeight;
}

/* ──────────────────────────────────────────────────────────────────────────
   Ollama Local AI Management
   ────────────────────────────────────────────────────────────────────────── */

async function refreshOllamaStatus() {
  if (!window.pywebview?.api) return;
  try {
    const status = await window.pywebview.api.check_ollama_status();
    const srvText = document.getElementById("ollama-service-status");
    const installedBadge = document.getElementById("ollama-installed-badge");
    const installBtn = document.getElementById("btn-install-model");
    const deleteBtn = document.getElementById("btn-delete-model");
    const chatDot = document.getElementById("ollama-dot");
    const chatText = document.getElementById("ollama-text");

    const isInstalled = !!status?.model_installed;
    const isRunning = !!status?.running;

    if (chatDot && chatText) {
      if (isInstalled) {
        chatDot.className = "status-dot";
        chatText.textContent = "Local Clinical AI Ready (llama3.2:3b)";
      } else if (isRunning) {
        chatDot.className = "status-dot";
        chatText.textContent = "Downloading Model...";
      } else {
        chatDot.className = "status-dot offline";
        chatText.textContent = "Offline Medical Rules Active";
      }
    }

    if (srvText) {
      if (isInstalled) {
        srvText.textContent = "Stopped (Model llama3.2:3b Installed & Ready)";
        srvText.style.color = "var(--accent-emerald)";
      } else if (isRunning) {
        srvText.textContent = "Running (Downloading model...)";
        srvText.style.color = "var(--secondary-light)";
      } else {
        srvText.textContent = "Stopped (Starts only during model download)";
        srvText.style.color = "var(--secondary-light)";
      }
    }

    if (installedBadge) {
      installedBadge.style.display = "inline-block";
      if (isInstalled) {
        installedBadge.textContent = "llama3.2:3b Ready";
        installedBadge.className = "risk-badge badge-low";
      } else {
        installedBadge.textContent = "Model Not Installed";
        installedBadge.className = "risk-badge badge-moderate";
      }
    }

    if (deleteBtn) {
      deleteBtn.style.display = isInstalled ? "inline-flex" : "none";
    }

    if (installBtn && !installBtn.disabled) {
      if (isInstalled) {
        installBtn.textContent = "✅ llama3.2:3b Installed";
      } else {
        installBtn.textContent = "⬇️ 1-Click Install llama3.2:3b Model";
      }
    }

    try {
      const dlState = await window.pywebview.api.get_model_download_progress();
      if (dlState) {
        if (dlState.status === "downloading" || dlState.status === "starting") {
          pollDownloadProgress();
        } else {
          updateDownloadUI(dlState, isInstalled);
        }
      }
    } catch (_) {}
  } catch (err) {
    console.error("Failed to check Ollama:", err);
    const srvText = document.getElementById("ollama-service-status");
    if (srvText) {
      srvText.textContent = "Stopped (Offline Medical Rules Active)";
      srvText.style.color = "var(--secondary-light)";
    }
    const chatText = document.getElementById("ollama-text");
    if (chatText) {
      chatText.textContent = "Offline Medical Rules Active";
    }
  }
}

function updateDownloadUI(state, isModelInstalled = false) {
  const fill = document.getElementById("model-progress-fill");
  const text = document.getElementById("model-progress-text");
  const installBtn = document.getElementById("btn-install-model");
  const pauseBtn = document.getElementById("btn-pause-model");
  const cancelBtn = document.getElementById("btn-cancel-model");
  const deleteBtn = document.getElementById("btn-delete-model");

  if (!fill || !text || !installBtn) return;

  const pct = typeof state.percent === "number" ? Math.max(0, Math.min(100, state.percent)) : 0;

  if (state.status === "downloading" || state.status === "starting") {
    fill.style.width = `${Math.max(pct, 2)}%`;
    text.textContent = state.message || "Downloading model...";
    installBtn.style.display = "none";
    if (deleteBtn) deleteBtn.style.display = "none";
    if (pauseBtn) {
      pauseBtn.style.display = "inline-flex";
      pauseBtn.disabled = false;
      pauseBtn.textContent = "⏸️ Pause";
    }
    if (cancelBtn) {
      cancelBtn.style.display = "inline-flex";
      cancelBtn.disabled = false;
      cancelBtn.textContent = "🛑 Cancel";
    }
  } else if (state.status === "paused") {
    fill.style.width = `${pct}%`;
    text.textContent = state.message || `Download paused at ${pct}%. Click Resume to continue.`;
    installBtn.style.display = "inline-flex";
    installBtn.disabled = false;
    installBtn.textContent = `▶️ Resume Download (${pct}%)`;
    if (deleteBtn) deleteBtn.style.display = "none";
    if (pauseBtn) pauseBtn.style.display = "none";
    if (cancelBtn) {
      cancelBtn.style.display = "inline-flex";
      cancelBtn.disabled = false;
      cancelBtn.textContent = "🛑 Cancel";
    }
  } else if (state.status === "success" || isModelInstalled) {
    fill.style.width = "100%";
    text.textContent = state.message || "✅ Model llama3.2:3b successfully installed and ready.";
    installBtn.style.display = "inline-flex";
    installBtn.disabled = false;
    installBtn.textContent = "✅ llama3.2:3b Installed";
    if (deleteBtn) deleteBtn.style.display = "inline-flex";
    if (pauseBtn) pauseBtn.style.display = "none";
    if (cancelBtn) cancelBtn.style.display = "none";
  } else {
    fill.style.width = state.status === "cancelled" ? "0%" : `${pct}%`;
    text.textContent = state.message || "Status: Ready to install";
    installBtn.style.display = "inline-flex";
    installBtn.disabled = false;
    installBtn.textContent = "⬇️ 1-Click Install llama3.2:3b Model";
    if (deleteBtn) deleteBtn.style.display = "none";
    if (pauseBtn) pauseBtn.style.display = "none";
    if (cancelBtn) cancelBtn.style.display = "none";
  }
}

async function deleteOllamaModel() {
  if (!window.pywebview?.api) return;

  showConfirmModal({
    title: "Delete AI Model",
    message: "Are you sure you want to permanently delete the llama3.2:3b model from this device? This will free up ~2 GB of storage.",
    confirmText: "Yes, Delete Model",
    isDanger: true,
    onConfirm: async () => {
      const deleteBtn = document.getElementById("btn-delete-model");
      if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = "⏳ Deleting...";
      }
      try {
        const res = await window.pywebview.api.delete_model("llama3.2:3b");
        await refreshOllamaStatus();
        showClinicalModal(res?.message || "Model llama3.2:3b was permanently removed from your device.");
      } catch (err) {
        showClinicalModal("Failed to delete model: " + err);
      } finally {
        if (deleteBtn) {
          deleteBtn.disabled = false;
          deleteBtn.textContent = "🗑️ Delete Model";
        }
      }
    }
  });
}

async function installOllamaModel() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById("btn-install-model");
  if (btn) btn.disabled = true;

  try {
    const progress = await window.pywebview.api.get_model_download_progress();
    let res;
    if (progress && progress.status === "paused") {
      res = await window.pywebview.api.resume_model_download("llama3.2:3b");
    } else {
      res = await window.pywebview.api.start_model_download("llama3.2:3b");
    }

    if (res.status === "started" || res.status === "resumed" || res.status === "busy") {
      pollDownloadProgress();
    } else {
      alert("Download status: " + (res.message || res.status));
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    alert("Failed to start/resume download: " + err);
    if (btn) btn.disabled = false;
  }
}

async function pauseOllamaDownload() {
  if (!window.pywebview?.api) return;
  const pauseBtn = document.getElementById("btn-pause-model");
  if (pauseBtn) {
    pauseBtn.disabled = true;
    pauseBtn.textContent = "⏳ Pausing...";
  }
  if (downloadPollTimer) {
    clearInterval(downloadPollTimer);
    downloadPollTimer = null;
  }
  try {
    const res = await window.pywebview.api.pause_model_download();
    if (res && res.state) {
      updateDownloadUI(res.state);
    } else {
      const state = await window.pywebview.api.get_model_download_progress();
      updateDownloadUI(state || { status: "paused" });
    }
  } catch (err) {
    console.error("Failed to pause download:", err);
  }
}

async function cancelOllamaDownload() {
  if (!window.pywebview?.api) return;
  const cancelBtn = document.getElementById("btn-cancel-model");
  if (cancelBtn) {
    cancelBtn.disabled = true;
    cancelBtn.textContent = "⏳ Cancelling...";
  }
  if (downloadPollTimer) {
    clearInterval(downloadPollTimer);
    downloadPollTimer = null;
  }
  try {
    await window.pywebview.api.cancel_model_download();
    const state = await window.pywebview.api.get_model_download_progress();
    updateDownloadUI(state || { status: "idle" });
  } catch (err) {
    console.error("Failed to cancel download:", err);
  }
}

function pollDownloadProgress() {
  if (downloadPollTimer) clearInterval(downloadPollTimer);

  downloadPollTimer = setInterval(async () => {
    try {
      const state = await window.pywebview.api.get_model_download_progress();
      updateDownloadUI(state);

      if (state.status === "success") {
        clearInterval(downloadPollTimer);
        downloadPollTimer = null;
        try {
          await window.pywebview.api.terminate_ollama();
        } catch (_) {}
        refreshOllamaStatus();
      } else if (state.status === "error") {
        clearInterval(downloadPollTimer);
        downloadPollTimer = null;
        alert("Download failed: " + (state.error || state.message));
      } else if (state.status === "paused" || state.status === "idle" || state.status === "cancelled") {
        clearInterval(downloadPollTimer);
        downloadPollTimer = null;
      }
    } catch (err) {
      clearInterval(downloadPollTimer);
      downloadPollTimer = null;
    }
  }, 600);
}

/* ──────────────────────────────────────────────────────────────────────────
   Saved Reports Management
   ────────────────────────────────────────────────────────────────────────── */

async function refreshSavedReports() {
  if (!window.pywebview?.api) return;
  try {
    const reports = await window.pywebview.api.list_saved_reports();
    const container = document.getElementById("saved-reports-list");
    if (!container) return;

    if (!reports || reports.length === 0) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">No saved reports yet.</div>';
      return;
    }

    container.innerHTML = reports
      .map(
        (r) => `
      <div class="report-item">
        <div>
          <div class="report-title">${r.is_html ? "📄" : "📊"} ${r.filename}</div>
          <div class="report-meta">${r.modified} | ${r.size_kb} KB</div>
        </div>
        <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px;" onclick="openReportsFolder()">
          Open Folder
        </button>
      </div>
    `
      )
      .join("");
  } catch (err) {
    console.error("Failed to list saved reports:", err);
  }
}

async function openReportsFolder() {
  if (!window.pywebview?.api) return;
  try {
    await window.pywebview.api.open_reports_folder();
  } catch (err) {
    alert("Could not open folder: " + err);
  }
}
