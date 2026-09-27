/**
 * Nutriloop - Desktop GUI Frontend Logic
 * Interfaces with Python backend via window.pywebview.api
 */

// Global State
let currentWeeklyPlan = null;
let chatHistory = [];
let downloadPollTimer = null;

// Wait for pywebview bridge readiness
window.addEventListener("pywebviewready", () => {
  console.log("Nutriloop Desktop Bridge Ready");
  initApp();
});

// Fallback initialization if opened directly
window.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  // If pywebview isn't ready in 500ms, check if api is already attached
  setTimeout(() => {
    if (window.pywebview && window.pywebview.api) {
      initApp();
    }
  }, 300);
});

async function initApp() {
  await loadSystemInfo();
  await checkAndLoadInitialPatient();
  await refreshOllamaStatus();
  await refreshSavedReports();
  await loadAiSettings();
  setupEventListeners();
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

let activeSelectedTest = { is_latest: true, date: null, id: null };

async function loadSystemInfo() {
  if (!window.pywebview?.api) return;
  try {
    const info = await window.pywebview.api.get_system_info();
    const dataDir = info.user_data_dir || "./";
    const dirLabel = document.getElementById("data-dir-label");
    if (dirLabel) dirLabel.textContent = dataDir.length > 25 ? "..." + dataDir.slice(-22) : dataDir;
    if (document.getElementById("settings-data-dir")) document.getElementById("settings-data-dir").value = dataDir;
    if (document.getElementById("settings-db-path")) document.getElementById("settings-db-path").value = info.db_path || "app_data.db";
  } catch (err) {
    console.error("Failed to load system info:", err);
  }
}

function applySafeClinicalDefaults() {
  const userEl = document.getElementById("p-user-id");
  if (userEl) userEl.value = "John Doe";
  if (document.getElementById("p-age")) document.getElementById("p-age").value = 45;
  if (document.getElementById("p-sex")) document.getElementById("p-sex").value = "male";
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
}

async function populatePatientTestHistory(userId = null, selectTestId = null) {
  if (!window.pywebview?.api) return;
  try {
    const currentId = userId || document.getElementById("p-user-id").value || "";
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
    const currentId = document.getElementById("p-user-id").value || "";
    const res = await window.pywebview.api.get_latest_test(currentId);
    if (res && res.found) {
      populateFormWithPatient(res);
      await populatePatientTestHistory(res.user_id, res.id);
      if (res.assessments && Object.keys(res.assessments).length > 0) {
        currentAssessmentData = res.assessments;
        renderAssessmentResults({ assessments: res.assessments, detected_conditions: res.detected_conditions });
        selectExplainDisease(activeExplainDisease);
        document.getElementById("assessment-status-badge").style.display = "inline-block";
      }
      activeSelectedTest = { is_latest: true, date: res.created_at, id: res.id };
    } else {
      applySafeClinicalDefaults();
      await populatePatientTestHistory(document.getElementById("p-user-id").value);
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
  if (p.age_years) document.getElementById("p-age").value = p.age_years;
  if (p.sex) document.getElementById("p-sex").value = p.sex.toLowerCase();
  if (p.body_mass_index) document.getElementById("p-bmi").value = p.body_mass_index;

  const labs = p.test_reports || p.raw_inputs || p;
  if (labs.systolic_bp_mmhg != null) document.getElementById("p-sbp").value = labs.systolic_bp_mmhg;
  if (labs.diastolic_bp_mmhg != null) document.getElementById("p-dbp").value = labs.diastolic_bp_mmhg;
  if (labs.fasting_glucose_mg_dl != null) document.getElementById("p-fbg").value = labs.fasting_glucose_mg_dl;
  if (labs.hba1c_pct != null) document.getElementById("p-hba1c").value = labs.hba1c_pct;
  if (labs.serum_creatinine_mg_dl != null) document.getElementById("p-creat").value = labs.serum_creatinine_mg_dl;
  if (labs.egfr_ml_min != null) document.getElementById("p-egfr").value = labs.egfr_ml_min;
  if (labs.serum_potassium_meq_l != null) document.getElementById("p-pot").value = labs.serum_potassium_meq_l;
  const sumEl = document.getElementById("p-summary");
  if (sumEl && labs.report_summary_text != null) sumEl.value = labs.report_summary_text;
}

/* ──────────────────────────────────────────────────────────────────────────
   Custom Confirmation Modal Card
   ────────────────────────────────────────────────────────────────────────── */

let confirmCallback = null;

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
   Multi-Disease Risk Assessment
   ────────────────────────────────────────────────────────────────────────── */

function setupEventListeners() {
  document.getElementById("btn-assess-patient").addEventListener("click", runAssessment);
  document.getElementById("btn-transfer-diet").addEventListener("click", () => {
    switchTab("tab-diet");
  });

  document.getElementById("btn-generate-diet").addEventListener("click", runWeeklyDiet);
  document.getElementById("btn-save-diet").addEventListener("click", saveWeeklyDiet);
  document.getElementById("btn-open-folder-diet").addEventListener("click", openReportsFolder);
  document.getElementById("btn-open-folder").addEventListener("click", openReportsFolder);

  document.getElementById("btn-chat-send").addEventListener("click", sendChatMessage);
  document.getElementById("chat-input-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
  document.getElementById("btn-save-ai-key")?.addEventListener("click", saveAiSettings);
  document.getElementById("ai-engine-select")?.addEventListener("change", () => {
    saveAiSettings();
  });

  document.getElementById("btn-refresh-ollama").addEventListener("click", refreshOllamaStatus);
  document.getElementById("btn-install-model").addEventListener("click", installOllamaModel);

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

  // User ID Change updates history dropdown for that patient
  document.getElementById("p-user-id")?.addEventListener("change", () => {
    populatePatientTestHistory(document.getElementById("p-user-id").value || "John Doe");
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
        document.getElementById("assessment-status-badge").style.display = "inline-block";
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

let modalTargetField = null;

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
   Multi-Disease Risk Assessment & Explainability
   ────────────────────────────────────────────────────────────────────────── */

let currentAssessmentData = null;
let activeExplainDisease = "ckd";

async function runAssessment() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById("btn-assess-patient");

  const age = parseFloat(document.getElementById("p-age").value);
  const bmi = parseFloat(document.getElementById("p-bmi").value);
  const sbp = parseFloat(document.getElementById("p-sbp").value);
  const dbp = parseFloat(document.getElementById("p-dbp").value);
  const fbg = parseFloat(document.getElementById("p-fbg").value);
  const hba1c = parseFloat(document.getElementById("p-hba1c").value);
  const creat = parseFloat(document.getElementById("p-creat").value);
  const egfr = parseFloat(document.getElementById("p-egfr").value);
  const pot = parseFloat(document.getElementById("p-pot").value);
  const sod = parseFloat(document.getElementById("p-sod").value);

  // 1. Proactive Physiological Boundary Checks with Medical Rationale
  if (!isNaN(fbg) && fbg < 40) {
    showClinicalModal(
      `Fasting Blood Glucose (${fbg} mg/dL) is physiologically impossible for outpatient clinical assessment.\n\n` +
      `Clinically, a fasting glucose below 40 mg/dL represents severe, life-threatening neuroglycopenic hypoglycemia ` +
      `(diabetic shock / neuroglycopenic coma) requiring immediate emergency medical resuscitation, not routine chronic disease diet planning.\n\n` +
      `Please check if this was a typographical data-entry error (e.g. intended 120 or 200 mg/dL).\n` +
      `• Permitted clinical range: 40 to 450 mg/dL\n` +
      `• Normal fasting reference: 70 to 99 mg/dL`,
      "p-fbg"
    );
    return;
  }
  if (!isNaN(fbg) && fbg > 450) {
    showClinicalModal(
      `Fasting Blood Glucose (${fbg} mg/dL) exceeds outpatient laboratory limits (> 450 mg/dL).\n\n` +
      `A level above 450 mg/dL indicates an acute Hyperosmolar Hyperglycemic State (HHS) or severe Diabetic Ketoacidosis (DKA) ` +
      `demanding urgent emergency hospital admission.\n\n` +
      `• Permitted clinical range: 40 to 450 mg/dL`,
      "p-fbg"
    );
    return;
  }
  if (!isNaN(sbp) && (sbp < 70 || sbp > 260)) {
    showClinicalModal(
      `Systolic Blood Pressure (${sbp} mmHg) is outside physiological boundaries.\n\n` +
      (sbp < 70 ? "Systolic pressure below 70 mmHg indicates acute circulatory collapse / cardiogenic shock." : "Systolic pressure above 260 mmHg is an acute Hypertensive Emergency with imminent danger of intracranial hemorrhage or aortic dissection.") +
      `\n\n• Permitted clinical range: 70 to 260 mmHg\n• Ideal normotensive target: < 120 mmHg`,
      "p-sbp"
    );
    return;
  }
  if (!isNaN(dbp) && (dbp < 40 || dbp > 160)) {
    showClinicalModal(
      `Diastolic Blood Pressure (${dbp} mmHg) is outside physiological boundaries.\n\n` +
      (dbp < 40 ? "Diastolic pressure below 40 mmHg compromises vital organ coronary perfusion." : "Diastolic pressure above 160 mmHg reflects malignant hypertensive vascular resistance.") +
      `\n\n• Permitted clinical range: 40 to 160 mmHg\n• Ideal normotensive target: < 80 mmHg`,
      "p-dbp"
    );
    return;
  }
  if (!isNaN(creat) && (creat < 0.1 || creat > 25.0)) {
    showClinicalModal(
      `Serum Creatinine (${creat} mg/dL) is outside clinical parameters.\n\n` +
      (creat < 0.1 ? "Values below 0.1 mg/dL fall beneath human metabolic muscle turnover." : "Values above 25 mg/dL indicate end-stage anuric renal failure requiring acute hemodialysis.") +
      `\n\n• Permitted clinical range: 0.1 to 25.0 mg/dL\n• Normal adult reference: 0.6 to 1.2 mg/dL`,
      "p-creat"
    );
    return;
  }
  if (!isNaN(age) && (age < 18 || age > 100)) {
    showClinicalModal(
      `Patient Age (${age} years) is outside the calibrated adult assessment scope.\n\n` +
      `This clinical nutrition software is calibrated for adult patients aged 18 to 100 years. Pediatric patients require specialized pediatric nephrology protocols.`,
      "p-age"
    );
    return;
  }
  if (!isNaN(bmi) && (bmi < 10.0 || bmi > 90.0)) {
    showClinicalModal(
      `Body Mass Index (${bmi} kg/m²) is out of bounds (valid range: 10.0 to 90.0 kg/m²). Please verify patient height and weight.`,
      "p-bmi"
    );
    return;
  }
  if (!isNaN(sod) && (sod < 100 || sod > 180)) {
    showClinicalModal(
      `Serum Sodium (${sod} mEq/L) is outside human physiological boundaries (100 to 180 mEq/L).\n\n` +
      `A blood serum sodium of ${sod} mEq/L is biologically impossible in outpatient clinical medicine.\n\n` +
      `• Normal adult blood sodium: 135 to 145 mEq/L (healthy baseline is ~140 mEq/L).\n` +
      `• Did you enter dietary sodium in milligrams (e.g. 1000 mg salt) instead of blood Serum Sodium (mEq/L)?\n\n` +
      `Please enter a valid laboratory blood test result between 100 and 180 mEq/L.`,
      "p-sod"
    );
    return;
  }
  if (!isNaN(pot) && (pot < 2.0 || pot > 8.5)) {
    showClinicalModal(
      `Serum Potassium (${pot} mEq/L) is outside human physiological boundaries (2.0 to 8.5 mEq/L).\n\n` +
      (pot < 2.0 ? "Potassium below 2.0 mEq/L induces severe cardiac arrhythmias and flaccid muscle paralysis." : "Potassium above 8.5 mEq/L induces fatal cardiac conduction arrest (asystole).") +
      `\n\n• Normal reference range: 3.5 to 5.0 mEq/L`,
      "p-pot"
    );
    return;
  }
  if (!isNaN(hba1c) && (hba1c < 3.0 || hba1c > 20.0)) {
    showClinicalModal(
      `HbA1c (${hba1c}%) is outside clinical laboratory limits (3.0% to 20.0%).\n\n` +
      `• Normal reference: < 5.7%\n• Prediabetes: 5.7% to 6.4%\n• Diabetes: ≥ 6.5%`,
      "p-hba1c"
    );
    return;
  }
  if (!isNaN(egfr) && (egfr < 5.0 || egfr > 160.0)) {
    showClinicalModal(
      `Estimated GFR (${egfr} mL/min) is outside valid clinical limits (5 to 160 mL/min).\n\n` +
      `• Optimal healthy clearance: ≥ 90 mL/min\n• Stage 3 CKD: 30 to 59 mL/min\n• Stage 5 Kidney Failure: < 15 mL/min`,
      "p-egfr"
    );
    return;
  }

  btn.disabled = true;
  btn.textContent = "⏳ Computing Risk Diagnostics...";

  const payload = {
    user_id: document.getElementById("p-user-id").value,
    age_years: isNaN(age) ? 45 : age,
    sex: document.getElementById("p-sex").value,
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
      document.getElementById("assessment-status-badge").style.display = "inline-block";

      // Refresh patient test history dropdown with new test selected as latest
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
    btn.disabled = false;
    btn.textContent = "⚡ Run Multi-Disease Risk Assessment";
  }
}

function renderAssessmentResults(res) {
  const ass = res.assessments;

  // CKD
  updateRiskMeter("ckd", ass.ckd);
  // Hypertension
  updateRiskMeter("hypertension", ass.hypertension);
  // Diabetes
  updateRiskMeter("diabetes", ass.diabetes);

  // Conditions Tags
  const condContainer = document.getElementById("detected-conditions-tags");
  condContainer.innerHTML = "";
  if (res.detected_conditions && res.detected_conditions.length > 0) {
    res.detected_conditions.forEach((c) => {
      const tag = document.createElement("span");
      tag.className = "brand-badge";
      tag.style.background = "rgba(244, 63, 94, 0.15)";
      tag.style.borderColor = "var(--accent-rose)";
      tag.style.color = "var(--accent-rose)";
      tag.textContent = "⚠️ " + c;
      condContainer.appendChild(tag);
    });
  } else {
    condContainer.innerHTML = '<span class="risk-badge badge-low">✅ No High Clinical Comorbidities Detected</span>';
  }
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
      <div style="color: var(--text-subtle); font-size: 12px; padding: 16px; text-align: center;">
        Awaiting patient evaluation. Run assessment to view tailored clinical explanations and actionable recommendations.
      </div>`;
    return;
  }

  const item = currentAssessmentData[dis];
  if (item.error) {
    container.innerHTML = `
      <div class="explain-section level-high-why">
        <div class="explain-section-header">⚠️ Clinical Evaluation Notice</div>
        <div style="font-size: 12.5px; color: #fca5a5; line-height: 1.5;">${item.error}</div>
      </div>`;
    return;
  }

  const exp = item.explanation || {};
  const level = (item.risk_level || "low").toLowerCase();
  const pct = ((item.risk_score || 0) * 100).toFixed(1);
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
    <!-- Top Disease & Status Summary Bar -->
    <div class="explain-meta-bar">
      <div class="explain-disease-title">
        ${dName}
      </div>
      <span class="risk-badge badge-${level}">
        ${statusIcon} ${level.toUpperCase()} RISK (${pct}%)
      </span>
    </div>

    <!-- 1. Result Explanation: Why is it so / What is working well -->
    <div class="explain-section level-${level}-why">
      <div class="explain-section-header">
        <span>${whyIcon} ${whyTitle}</span>
      </div>
      <ul class="explain-list">
        ${whyReasonsHtml}
      </ul>
    </div>

    <!-- 2. Action Plan: What to do / How to reduce it / Steps to preserve it -->
    <div class="explain-section level-${level}-action">
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

  if (!data || data.error) {
    scoreNum.textContent = "ERR";
    badge.textContent = "NOTICE";
    badge.className = "risk-badge badge-high";
    return;
  }

  const scorePct = (data.risk_score * 100).toFixed(1);
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
  btn.disabled = true;
  btn.textContent = "⏳ Assembling Personalized 7-Day Plan...";

  const likes = document.getElementById("diet-likes").value.split(",").map((s) => s.trim()).filter(Boolean);
  const dislikesRaw = document.getElementById("diet-dislikes").value.split(",").map((s) => s.trim()).filter(Boolean);
  const meds = document.getElementById("diet-meds").value.split(",").map((s) => s.trim()).filter(Boolean);
  const craving = document.getElementById("diet-craving")?.value.trim() || "";

  const payload = {
    user_id: document.getElementById("p-user-id").value,
    age_years: parseFloat(document.getElementById("p-age").value) || 45,
    sex: document.getElementById("p-sex").value,
    body_mass_index: parseFloat(document.getElementById("p-bmi").value) || 22.0,
    test_reports: {
      systolic_bp_mmhg: parseFloat(document.getElementById("p-sbp").value) || 115,
      diastolic_bp_mmhg: parseFloat(document.getElementById("p-dbp").value) || 75,
      fasting_glucose_mg_dl: parseFloat(document.getElementById("p-fbg").value) || 90,
      hba1c_pct: parseFloat(document.getElementById("p-hba1c").value) || 5.2,
      serum_creatinine_mg_dl: parseFloat(document.getElementById("p-creat").value) || 0.9,
      egfr_ml_min: parseFloat(document.getElementById("p-egfr").value) || 100,
      serum_potassium_meq_l: parseFloat(document.getElementById("p-pot").value) || 4.2,
      serum_sodium_meq_l: parseFloat(document.getElementById("p-sod").value) || 140,
      report_summary_text: document.getElementById("p-summary")?.value || "",
    },
    preferences: {
      native_place_region: document.getElementById("diet-region").value,
      dietary_type: (document.getElementById("diet-type").value || "vegetarian").replace("-", "_"),
      calorie_target_kcal: document.getElementById("diet-calories").value.trim() ? parseInt(document.getElementById("diet-calories").value, 10) : null,
      calorie_target_override: document.getElementById("diet-calories").value.trim() ? parseInt(document.getElementById("diet-calories").value, 10) : null,
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
    btn.disabled = false;
    btn.textContent = "✨ Generate 7-Day Medical Nutrition Plan";
  }
}

function renderWeeklyDietResults(plan) {
  const container = document.getElementById("weekly-plan-results");
  container.style.display = "block";

  // Smart Craving Strategy Box
  const cravingBox = document.getElementById("diet-craving-box");
  if (cravingBox) {
    if (plan.smart_craving_strategy && plan.smart_craving_strategy.requested_craving) {
      const cs = plan.smart_craving_strategy;
      cravingBox.style.display = "block";
      cravingBox.innerHTML = `
        <h4>🎯 Smart Craving Optimization <span class="craving-badge">${cs.requested_craving}</span></h4>
        <p style="margin-bottom: 6px;"><strong>Scheduled Indulgence:</strong> ${cs.scheduled_day} (${cs.scheduled_meal}) — <em>${cs.indulgence_title}</em></p>
        <p style="font-size: 12.5px; opacity: 0.9; margin-bottom: 4px;">⚖️ <strong>Weekly Metabolic Balance:</strong> ${cs.metabolic_rebalance_note}</p>
        <p style="font-size: 12px; color: #93c5fd;">🔒 <strong>Strict Non-Treat Days:</strong> Days 1–6 are strictly optimized with zero sugar / zero indulgence to protect your metabolic targets.</p>
      `;
    } else {
      cravingBox.style.display = "none";
    }
  }

  // Medication Alerts
  const medAlertsBox = document.getElementById("diet-med-alerts");
  const medAlerts = plan.medication_alerts || plan.active_medication_alerts || [];
  if (medAlerts.length > 0) {
    medAlertsBox.style.display = "block";
    let alertsHtml = "<h4>⚠️ Critical Pharmacopeia & Medication Contraindications</h4><ul>";
    medAlerts.forEach((a) => {
      alertsHtml += `<li>${a}</li>`;
    });
    alertsHtml += "</ul>";
    medAlertsBox.innerHTML = alertsHtml;
  } else {
    medAlertsBox.style.display = "none";
  }

  // Targets Row
  const targetsRow = document.getElementById("diet-targets-row");
  const t = plan.clinical_targets || {};
  targetsRow.innerHTML = `
    <div class="target-badge">
      <div class="target-value">${t.calories_kcal || 1800} kcal</div>
      <div class="target-label">Caloric Target</div>
    </div>
    <div class="target-badge">
      <div class="target-value">${t.protein_g || 60} g</div>
      <div class="target-label">Protein Target</div>
    </div>
    <div class="target-badge">
      <div class="target-value">${t.carbohydrate_g || 220} g</div>
      <div class="target-label">Carbohydrate Floor</div>
    </div>
    <div class="target-badge">
      <div class="target-value">${t.fat_g || 50} g</div>
      <div class="target-label">Healthy Fats</div>
    </div>
    <div class="target-badge">
      <div class="target-value">&ge; ${t.fiber_target_g || 28} g</div>
      <div class="target-label">Dietary Fiber</div>
    </div>
    <div class="target-badge">
      <div class="target-value">&le; ${t.sodium_limit_mg || 1500} mg</div>
      <div class="target-label">Sodium Limit</div>
    </div>
    <div class="target-badge">
      <div class="target-value">&le; ${t.potassium_guidance_mg || 2000} mg</div>
      <div class="target-label">Potassium Guidance</div>
    </div>
    <div class="target-badge">
      <div class="target-value">${t.fluid_intake_ml || 2000} ml</div>
      <div class="target-label">Fluid Intake</div>
    </div>
    <div class="target-badge">
      <div class="target-value">${plan.regional_cuisine || "Regional"}</div>
      <div class="target-label">Cuisine Tradition</div>
    </div>
  `;

  // Render 7 Days
  const daysList = document.getElementById("diet-days-list");
  daysList.innerHTML = "";

  plan.days.forEach((day, idx) => {
    const strip = document.createElement("div");
    strip.className = `day-strip ${idx === 0 ? "open" : ""}`;

    const tot = day.daily_total_nutrients || {};
    strip.innerHTML = `
      <div class="day-strip-header" onclick="this.parentElement.classList.toggle('open')">
        <div style="font-weight: 700; color: #ffffff;">
          Day ${day.day_number}: ${day.day_name}
        </div>
        <div style="font-size: 12.5px; color: var(--text-muted);">
          ${tot.calories || "-"} kcal | P: ${tot.protein_g || "-"}g | Na: ${tot.sodium_mg || "-"}mg | K: ${tot.potassium_mg || "-"}mg
        </div>
      </div>
      <div class="day-intervals-container" style="${idx === 0 ? 'display:flex;' : 'display:none;'}">
        ${renderDayIntervals(day.intervals)}
      </div>
    `;

    // Toggle logic
    const header = strip.querySelector(".day-strip-header");
    header.addEventListener("click", () => {
      const container = strip.querySelector(".day-intervals-container");
      if (strip.classList.contains("open")) {
        strip.classList.remove("open");
        container.style.display = "none";
      } else {
        strip.classList.add("open");
        container.style.display = "flex";
      }
    });

    daysList.appendChild(strip);
  });

  // Grocery Checklist
  const groceryContainer = document.getElementById("diet-grocery-list");
  if (plan.categorized_grocery_checklist && Object.keys(plan.categorized_grocery_checklist).length > 0) {
    let catHtml = `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; width: 100%;">`;
    for (const [catName, items] of Object.entries(plan.categorized_grocery_checklist)) {
      if (items && items.length > 0) {
        catHtml += `
          <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 8px; padding: 12px 14px;">
            <div style="font-weight: 700; color: #60a5fa; font-size: 13px; margin-bottom: 8px;">${catName}</div>
            <ul style="margin: 0; padding-left: 18px; line-height: 1.6; font-size: 12.5px; color: #cbd5e1;">
              ${items.map((it) => `<li>${it}</li>`).join("")}
            </ul>
          </div>
        `;
      }
    }
    catHtml += `</div>`;
    groceryContainer.innerHTML = catHtml;
    groceryContainer.style.columns = "unset";
  } else if (plan.grocery_checklist && plan.grocery_checklist.length > 0) {
    groceryContainer.style.columns = "2";
    groceryContainer.innerHTML = plan.grocery_checklist.map((g) => `<li>${g}</li>`).join("");
  }
}

function renderDayIntervals(intervals) {
  return intervals
    .map((inv) => {
      const nut = inv.total_nutrients || {};
      const itemsStr = inv.items
        .map((it) => `• <strong>${it.item_name}</strong> (${it.portion})`)
        .join("<br>");

      const isStarred = (inv.meal_title || "").startsWith("⭐");
      const cleanTitle = (inv.meal_title || "").replace(/^⭐\s*/, "");
      const starBadge = isStarred
        ? `<span class="craving-badge" style="background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; color: #fbbf24; font-size: 11px; padding: 2px 7px; margin-left: 8px;">⭐ Preferred Choice</span>`
        : "";

      return `
      <div class="interval-box" style="${isStarred ? 'border-left: 3px solid #f59e0b;' : ''}">
        <div class="interval-header">
          <span class="interval-title">${inv.interval_name} (${inv.time_window}): <strong>${cleanTitle}</strong>${starBadge}</span>
          <span class="interval-nutri">${nut.calories || "-"} kcal | P: ${nut.protein_g || "-"}g | Na: ${nut.sodium_mg || "-"}mg</span>
        </div>
        <div class="interval-items">${itemsStr}</div>
        <div class="interval-clinical">💡 Clinical Note: ${inv.clinical_justification || "Balanced glycemic profile."}</div>
      </div>
    `;
    })
    .join("");
}

async function saveWeeklyDiet() {
  if (!currentWeeklyPlan || !window.pywebview?.api) return;
  const pid = document.getElementById("p-user-id").value || "patient";
  try {
    const res = await window.pywebview.api.save_weekly_diet_report(currentWeeklyPlan, pid);
    if (res.status === "saved") {
      alert(`Report saved locally to your folder:\n${res.filename}\n(Both JSON and printable HTML created)`);
      refreshSavedReports();
    }
  } catch (err) {
    alert("Failed to save report: " + err);
  }
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

  // Escape HTML tags to protect integrity
  let safe = rawText
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text** or __text__
  safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/__(.*?)__/g, "<strong>$1</strong>");

  // Italic *text* or _text_
  safe = safe.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  // Inline code `code`
  safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Headers
  safe = safe.replace(/^### (.*$)/gim, "<h4>$1</h4>");
  safe = safe.replace(/^## (.*$)/gim, "<h3>$1</h3>");

  // Process lines for lists and paragraphs
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
  if (inList) {
    html += "</ul>";
  }

  // Clean empty paragraphs and repeated breaks
  html = html.replace(/<p><\/p>/g, "").replace(/(<br>\s*){3,}/g, "<br><br>");
  return html;
}

function sendQuickPrompt(promptText) {
  document.getElementById("chat-input-text").value = promptText;
  sendChatMessage();
}

function updateChatGating(isModelInstalled) {
  const input = document.getElementById("chat-input-text");
  const sendBtn = document.getElementById("btn-chat-send");
  const chips = document.querySelectorAll(".chat-chips .chip-btn");

  if (input) {
    input.disabled = false;
    input.placeholder = "Ask about recipes, nutrients, safe meal ideas, or substitutions...";
  }

  if (sendBtn) {
    sendBtn.disabled = false;
  }

  chips.forEach((c) => {
    c.style.pointerEvents = "auto";
    c.style.opacity = "1";
  });
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input-text");
  const msg = input.value.trim();
  if (!msg) return;

  const btn = document.getElementById("btn-chat-send");
  btn.disabled = true;
  input.value = "";

  // Append user bubble
  appendChatBubble("user", msg);

  // Prepare payload
  const userId = document.getElementById("p-user-id").value || "patient_local";
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

    // If Dr. Nutriloop approved and altered the 7-day diet plan live
    if (res.updated_diet_plan) {
      currentWeeklyPlan = res.updated_diet_plan;
      renderWeeklyDietResults(res.updated_diet_plan);
      showClinicalModal("🩺 Dr. Nutriloop Prescription Notice:\n\nYour 7-Day Regional Nutrition Plan has been clinically updated based on your consultation. You can view the altered meal schedule in Tab 2.");
    }
  } catch (err) {
    appendChatBubble("assistant", "Chat service error: " + err, "Error", false);
  } finally {
    btn.disabled = false;
  }
}

function appendChatBubble(role, text, engineMode, isEscalated = false) {
  const container = document.getElementById("chat-messages-container");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-msg ${role} ${isEscalated ? "escalated" : ""}`;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.innerHTML = renderMarkdown(text);
  msgDiv.appendChild(bubble);

  const meta = document.createElement("div");
  meta.className = "chat-meta";
  if (role === "assistant") {
    const modeBadge = document.createElement("span");
    modeBadge.className = isEscalated ? "risk-badge badge-high" : "brand-badge";
    modeBadge.style.fontSize = "10px";
    modeBadge.textContent = isEscalated ? "🚨 Emergency Escalation" : (engineMode || "Nutriloop");
    meta.appendChild(modeBadge);
  }
  msgDiv.appendChild(meta);

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

/* ──────────────────────────────────────────────────────────────────────────
   Ollama Manager & Saved Reports
   ────────────────────────────────────────────────────────────────────────── */

async function refreshOllamaStatus() {
  if (!window.pywebview?.api) return;
  try {
    const status = await window.pywebview.api.check_ollama();
    const dot = document.getElementById("ollama-dot");
    const text = document.getElementById("ollama-text");
    const srvText = document.getElementById("ollama-service-status");
    const installedBadge = document.getElementById("ollama-installed-badge");
    const installBtn = document.getElementById("btn-install-model");

    // Enforce Chat Section Gating
    updateChatGating(status.model_installed);

    if (dot) dot.className = status.model_installed ? "status-dot" : "status-dot offline";
    if (text) text.textContent = status.model_installed ? "Dr. Nutriloop AI (llama3.2:3b)" : "Model Not Installed";

    if (srvText) {
      if (status.model_installed) {
        srvText.textContent = "Ready (llama3.2:3b Installed)";
        srvText.style.color = "var(--accent-emerald)";
      } else {
        srvText.textContent = "Model Missing";
        srvText.style.color = "var(--accent-amber)";
      }
    }

    if (installedBadge) {
      installedBadge.style.display = "inline-block";
      if (status.model_installed) {
        installedBadge.textContent = "llama3.2:3b Ready";
        installedBadge.className = "risk-badge badge-low";
      } else {
        installedBadge.textContent = "Model Missing";
        installedBadge.className = "risk-badge badge-moderate";
      }
    }

    if (installBtn && !installBtn.disabled) {
      if (status.model_installed) {
        installBtn.textContent = "✅ llama3.2:3b Installed (Re-install if needed)";
      } else {
        installBtn.textContent = "⬇️ 1-Click Install llama3.2:3b Model";
      }
    }
  } catch (err) {
    console.error("Failed to check Ollama:", err);
  }
}

async function installOllamaModel() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById("btn-install-model");
  btn.disabled = true;

  try {
    const res = await window.pywebview.api.start_model_download("llama3.2:3b");
    if (res.status === "started") {
      pollDownloadProgress();
    } else {
      alert("Download status: " + res.message);
      btn.disabled = false;
    }
  } catch (err) {
    alert("Failed to start download: " + err);
    btn.disabled = false;
  }
}

function pollDownloadProgress() {
  if (downloadPollTimer) clearInterval(downloadPollTimer);

  const fill = document.getElementById("model-progress-fill");
  const text = document.getElementById("model-progress-text");
  const btn = document.getElementById("btn-install-model");

  downloadPollTimer = setInterval(async () => {
    try {
      const state = await window.pywebview.api.get_model_download_progress();
      fill.style.width = `${state.percent}%`;
      text.textContent = state.message;

      if (state.status === "success") {
        clearInterval(downloadPollTimer);
        btn.disabled = false;
        btn.textContent = "✅ Model Installed (llama3.2:3b)";
        refreshOllamaStatus();
      } else if (state.status === "error") {
        clearInterval(downloadPollTimer);
        btn.disabled = false;
        alert("Download failed: " + (state.error || state.message));
      }
    } catch (err) {
      clearInterval(downloadPollTimer);
      btn.disabled = false;
    }
  }, 600);
}

async function refreshSavedReports() {
  if (!window.pywebview?.api) return;
  try {
    const reports = await window.pywebview.api.list_saved_reports();
    const container = document.getElementById("saved-reports-list");

    if (!reports || reports.length === 0) {
      container.innerHTML = '<div style="font-size: 12px; color: var(--text-subtle);">No saved reports yet.</div>';
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
