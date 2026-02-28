/* =====================================================
   AYUSH–ICD-11 PoC
   FINAL CLEAN DASHBOARD LOGIC
   ===================================================== */

const BASE_URL = "http://127.0.0.1:8000";

let patientResource = null;
let selectedCondition = null;

/* ================= CREATE PATIENT ================= */
document
  .getElementById("create-patient-btn")
  ?.addEventListener("click", async () => {
    const name = document.getElementById("patient-name").value.trim();
    const gender = document.getElementById("patient-gender").value.trim();
    const dob = document.getElementById("patient-dob").value;

    if (!name || !gender || !dob) {
      showToast("Fill all patient details");
      return;
    }

    try {
      const res = await fetch(`${BASE_URL}/fhir/patient`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, gender, birthDate: dob })
      });

      patientResource = await res.json();
      showToast("Patient created successfully");
    } catch {
      showToast("Error creating patient");
    }
  });

/* ================= SEARCH DISEASE ================= */
document
  .getElementById("search-disease-btn")
  ?.addEventListener("click", async () => {
    const query = document.getElementById("disease-query").value.trim();
    if (!query) {
      showToast("Enter disease to search");
      return;
    }

    const list = document.getElementById("disease-results");
    list.innerHTML = "";
    selectedCondition = null;

    try {
      const res = await fetch(
        `${BASE_URL}/search?term=${query}&system=ayurveda`
      );
      const data = await res.json();

      /* ---- NAMASTE RESULTS ---- */
      if (data.status === "success" && data.results.length > 0) {
        data.results.forEach(item => {
          const li = document.createElement("li");
          li.classList.add("disease-item");
          li.innerText = `${item.term} (${item.code})`;

          li.onclick = () => {
            /* hide all other NAMASTE options */
            document
              .querySelectorAll(".disease-item")
              .forEach(x => {
                if (x !== li) x.style.display = "none";
              });

            li.classList.add("selected");

            selectedCondition = {
              system: "ayurveda",
              term: item.term,
              finalCoding: null
            };

            updateCodePreview(item.term);
          };

          list.appendChild(li);
        });
        return;
      }

      /* ---- RULE BASED FALLBACK ---- */
      const li = document.createElement("li");
      li.classList.add("disease-item");
      li.innerText = `${query} (rule-based)`;

      li.onclick = () => {
        document
          .querySelectorAll(".disease-item")
          .forEach(x => {
            if (x !== li) x.style.display = "none";
          });

        li.classList.add("selected");

        selectedCondition = {
          system: "ayurveda",
          term: query,
          finalCoding: null
        };

        updateCodePreview(query);
      };

      list.appendChild(li);

    } catch {
      showToast("Error searching disease");
    }
  });

/* ================= CODE PREVIEW + ICD SELECTION ================= */
function updateCodePreview(term) {
  fetch(`${BASE_URL}/translate?system=ayurveda&term=${term}`)
    .then(res => res.json())
    .then(data => {
      const coding = data.code.coding;
      const preview = document.getElementById("code-preview");

      preview.innerHTML = `
        <li><b>AYUSH (NAMASTE):</b> ${coding[0].display}</li>
        <li><b>Select diagnosis interpretation:</b></li>

        <label id="tm2-option">
          <input type="radio" name="icdChoice">
          Traditional disorder (TM2): ${coding[1].code} – ${coding[1].display}
        </label><br>

        <label id="icd11-option">
          <input type="radio" name="icdChoice">
          Non-specific symptom (ICD-11): ${coding[2].code} – ${coding[2].display}
        </label>
      `;

      const tm2Radio = document.querySelector("#tm2-option input");
      const icd11Radio = document.querySelector("#icd11-option input");

      tm2Radio.onchange = () => {
        document.getElementById("icd11-option").style.display = "none";
        selectedCondition.finalCoding = coding[1];
      };

      icd11Radio.onchange = () => {
        document.getElementById("tm2-option").style.display = "none";
        selectedCondition.finalCoding = coding[2];
      };
    })
    .catch(() => showToast("Error loading code preview"));
}

/* ================= GENERATE FHIR REPORT ================= */
document
  .getElementById("generate-report-btn")
  ?.addEventListener("click", async () => {
    if (!patientResource || !selectedCondition?.finalCoding) {
      showToast("Select patient and diagnosis interpretation");
      return;
    }

    try {
      /* ---- CREATE CONDITION ---- */
      const condRes = await fetch(`${BASE_URL}/fhir/condition`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientResource.id,
          system: selectedCondition.system,
          term: selectedCondition.term
        })
      });

      const condition = await condRes.json();

      /* ---- OVERRIDE CODING WITH FINAL SELECTION ---- */
      condition.code.coding = [
        {
          system: "NAMASTE-AYURVEDA",
          display: selectedCondition.term
        },
        selectedCondition.finalCoding
      ];

      /* ---- GENERATE BUNDLE ---- */
      const bundleRes = await fetch(`${BASE_URL}/fhir/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient: patientResource,
          condition
        })
      });

      const bundle = await bundleRes.json();
      document.getElementById("report-output").innerText =
        JSON.stringify(bundle, null, 2);

      showToast("FHIR bundle generated successfully");
    } catch {
      showToast("Error generating FHIR bundle");
    }
  });
