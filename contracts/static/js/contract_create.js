let parties = [];
let editingIndex = null;
let currentStep = 1;
let clauseCount = 0;
let durationType = "fixed";

const CLAUSE_TYPES = [
    { value: "GENERAL", label: "عام" },
    { value: "PAYMENT", label: "دفع" },
    { value: "DELIVERY", label: "تسليم" },
    { value: "PENALTY", label: "غرامة" },
    { value: "CUSTOM", label: "مخصص" },
];

const PARTY_TYPE_LABELS = {
    INDIVIDUAL: "فرد",
    ORGANIZATION: "منشأة",
};

const SIGNING_ROLE_LABELS = {
    SIGNER: "موقّع — يوقع باسمه الشخصي",
    DELEGATED: "مفوّض — يوقع نيابةً عن منشأة أو جهة",
    REVIEWER: "مراجع — يراجع ويعلّق بدون توقيع",
};

const SIGNING_ROLE_HINTS = {
    SIGNER: "<strong>موقّع:</strong> طرف ملزَم قانونياً يوقع باسمه الشخصي. يحق له الاطلاع على العقد كاملاً والتوقيع عليه.",
    DELEGATED: "<strong>مفوّض:</strong> يوقع نيابةً عن شركة أو جهة. يجب تحديد صفته ومستند التفويض في بيانات المنشأة.",
    REVIEWER: "<strong>مراجع:</strong> يطّلع على العقد ويضيف ملاحظاته فقط — لا يُعدّ طرفاً ملزَماً ولا يوقع.",
};

const ARABIC_ORDINALS = [
    "الثاني",
    "الثالث",
    "الرابع",
    "الخامس",
    "السادس",
    "السابع",
    "الثامن",
    "التاسع",
    "العاشر",
];

const STEP_LABELS = [
    "",
    "معلومات العقد",
    "أطراف العقد",
    "بنود العقد",
    "المراجعة والتدقيق",
];

const CLAUSE_SECTIONS = ["obligations", "penalties", "termination"];

const SECTION_DEFAULT_TYPE = {
    obligations: "GENERAL",
    penalties: "PENALTY",
    termination: "CUSTOM",
};

function getLegalTitle(index) {
    return `الطرف ${ARABIC_ORDINALS[index] || `رقم ${index + 2}`}`;
}

function buildPartyNameMap() {
    const map = {
        "": "جميع الأطراف",
        PARTY_1: "الطرف الأول (المنشئ)",
    };

    parties.forEach((party, index) => {
        map[`PARTY_${index + 2}`] = getLegalTitle(index);
    });

    return map;
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(";").shift();
    }

    return "";
}

function getInitials(name) {
    return name
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0])
        .join("");
}

function esc(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getPermLabels(party) {
    const labels = [];

    if (party.can_view_contract) labels.push("عرض العقد");
    if (party.can_comment) labels.push("ملاحظات");
    if (party.can_edit) labels.push("تعديل");
    if (party.can_upload_files) labels.push("رفع مرفقات");
    if (party.can_sign) labels.push("التوقيع");

    return labels;
}

function setDurationType(type) {
    durationType = type;

    document.getElementById("toggle-fixed").classList.toggle("active", type === "fixed");
    document.getElementById("toggle-open").classList.toggle("active", type === "open");

    document.getElementById("duration-fixed").style.display =
        type === "fixed" ? "block" : "none";

    document.getElementById("duration-open").style.display =
        type === "open" ? "block" : "none";
}

function calcDuration() {
    const start = document.getElementById("start_date").value;
    const end = document.getElementById("end_date").value;
    const result = document.getElementById("duration-result");

    if (!start || !end) {
        result.style.display = "none";
        return;
    }

    const diffMs = new Date(end) - new Date(start);

    if (diffMs <= 0) {
        result.style.display = "block";
        result.textContent = " تاريخ النهاية يجب أن يكون بعد تاريخ البداية";
        return;
    }

    const days = Math.ceil(diffMs / 86400000);
    const months = Math.floor(days / 30);
    const years = Math.floor(days / 365);

    const label =
        years >= 1
            ? `${years} سنة (${days} يوم)`
            : months >= 1
            ? `${months} شهر (${days} يوم)`
            : `${days} يوم`;

    result.style.display = "block";
    result.innerHTML = ` مدة العقد: <strong>${label}</strong>`;
}

function formatValue(input) {
    if (input.value < 0) {
        input.value = 0;
    }
}

function goToStep(stepNumber) {
    if (stepNumber === 2 && !validateStep1()) return;
    if (stepNumber === 3 && !validateStep2()) return;
    if (stepNumber === 4 && !validateStep3()) return;

    document.getElementById(`panel-${currentStep}`).classList.remove("active");
    document.getElementById(`ws-${currentStep}`).classList.remove("active");

    if (stepNumber > currentStep) {
        document.getElementById(`ws-${currentStep}`).classList.add("completed");
        document.getElementById(`wc-${currentStep}`).innerHTML = "✓";
        document.getElementById(`wl-${currentStep}`)?.classList.add("done");
    }

    currentStep = stepNumber;

    document.getElementById(`ws-${stepNumber}`).classList.add("active");
    document.getElementById(`panel-${stepNumber}`).classList.add("active");
    document.getElementById("breadcrumb-step").textContent = STEP_LABELS[stepNumber];

    if (stepNumber === 4) {
        renderReview();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

function validateStep1() {
    let valid = true;

    const title = document.getElementById("title_ar").value.trim();
    const contractType = document.getElementById("contract_type").value;

    document.getElementById("err-title").classList.toggle("show", !title);
    document.getElementById("err-contract-type").classList.toggle("show", !contractType);

    if (!title || !contractType) valid = false;

    if (durationType === "fixed") {
        const start = document.getElementById("start_date").value;
        const end = document.getElementById("end_date").value;

        document.getElementById("err-start-date").classList.toggle("show", !start);

        if (!end || (start && new Date(end) <= new Date(start))) {
            document.getElementById("err-end-date").classList.add("show");
            valid = false;
        } else {
            document.getElementById("err-end-date").classList.remove("show");
        }
    }

    return valid;
}

function validateStep2() {
    const error = document.getElementById("parties-error");

    if (parties.length === 0) {
        error.textContent = "يجب إضافة طرف واحد على الأقل قبل المتابعة.";
        return false;
    }

    error.textContent = "";
    return true;
}

function validateStep3() {
    const container = document.getElementById("clauses-obligations");

    const hasObligation = Array.from(
        container?.querySelectorAll('[id^="ccontent-"]') || []
    ).some((textarea) => textarea.value.trim());

    document.getElementById("err-clauses").classList.toggle("show", !hasObligation);

    if (!hasObligation) {
        switchClauseTab("obligations");
        return false;
    }

    return true;
}

function switchClauseTab(section) {
    CLAUSE_SECTIONS.forEach((item) => {
        document.getElementById(`tab-${item}`)?.classList.toggle("active", item === section);
        document.getElementById(`section-${item}`)?.classList.toggle("active", item === section);
    });
}

function addClause(section = "obligations", content = "", type = null, assignedParty = "") {
    clauseCount++;

    const id = clauseCount;
    const defaultType = type || SECTION_DEFAULT_TYPE[section] || "GENERAL";
    const container = document.getElementById(`clauses-${section}`);

    if (!container) return;

    const partyNameMap = buildPartyNameMap();

    const partyOptions = Object.entries(partyNameMap)
        .map(
            ([key, label]) =>
                `<option value="${key}" ${assignedParty === key ? "selected" : ""}>${label}</option>`
        )
        .join("");

    const sectionCount = container.querySelectorAll(".clause-item").length + 1;

    const div = document.createElement("div");
    div.className = "clause-item";
    div.id = `clause-${id}`;
    div.dataset.section = section;

    div.innerHTML = `
        <div class="clause-header">
            <div class="clause-header-inner">
                <div class="clause-num">${sectionCount}</div>
                <select class="clause-type-sel" id="ctype-${id}">
                    ${CLAUSE_TYPES.map(
                        (item) =>
                            `<option value="${item.value}" ${
                                item.value === defaultType ? "selected" : ""
                            }>${item.label}</option>`
                    ).join("")}
                </select>
            </div>

            <button class="clause-del" onclick="removeClause(${id}, '${section}')">
                حذف
            </button>
        </div>

        <select id="cassigned-${id}" class="clause-assigned-select">
            ${partyOptions}
        </select>

        <textarea
            id="ccontent-${id}"
            rows="3"
            class="clause-textarea"
            placeholder="${getSectionPlaceholder(section)}"
        >${content}</textarea>
    `;

    container.appendChild(div);
    document.getElementById(`ccontent-${id}`).focus();
    document.getElementById("err-clauses").classList.remove("show");
}

function getSectionPlaceholder(section) {
    const placeholders = {
        obligations: "مثال: يلتزم الطرف الثاني بتسليم المنتج خلال 14 يوم عمل من تاريخ الإبرام...",
        penalties: "مثال: في حال التأخر عن موعد التسليم، يُلزم الطرف المخل بغرامة 2% من قيمة العقد عن كل أسبوع تأخير...",
        termination: "مثال: يحق لأي طرف إنهاء العقد بإشعار كتابي قبل 30 يوماً في حال إخلال الطرف الآخر بالتزاماته...",
    };

    return placeholders[section] || "اكتب نص البند هنا...";
}

function removeClause(id, section) {
    document.getElementById(`clause-${id}`)?.remove();

    document
        .getElementById(`clauses-${section}`)
        ?.querySelectorAll(".clause-num")
        .forEach((element, index) => {
            element.textContent = index + 1;
        });
}

function getClauses() {
    const clauses = [];

    CLAUSE_SECTIONS.forEach((section) => {
        const container = document.getElementById(`clauses-${section}`);

        if (!container) return;

        container.querySelectorAll('[id^="ccontent-"]').forEach((textarea) => {
            const number = textarea.id.split("-")[1];
            const content = textarea.value.trim();

            if (!content) return;

            clauses.push({
                content_ar: content,
                clause_type: document.getElementById(`ctype-${number}`)?.value || "GENERAL",
                assigned_party: document.getElementById(`cassigned-${number}`)?.value || "",
                section,
            });
        });
    });

    return clauses;
}
function openPartyModal(index = null) {
    editingIndex = index;

    const formError = document.getElementById("parties-error");
    const modalTitle = document.getElementById("modalTitle");
    const partyModal = document.getElementById("partyModal");

    formError.textContent = "";
    modalTitle.textContent = index === null ? "إضافة طرف" : "تعديل بيانات الطرف";

    if (index === null) {
        resetModal();
    } else {
        fillModal(parties[index]);
    }

    partyModal.classList.add("show");
    partyModal.setAttribute("aria-hidden", "false");
}

function closePartyModal() {
    const partyModal = document.getElementById("partyModal");

    partyModal.classList.remove("show");
    partyModal.setAttribute("aria-hidden", "true");
}

function applyRoleDefaults(role) {
    const isSigner = role === "SIGNER" || role === "DELEGATED";

    document.getElementById("canViewContract").checked = true;
    document.getElementById("canComment").checked = true;
    document.getElementById("canEdit").checked = false;
    document.getElementById("canUploadFiles").checked = false;
    document.getElementById("canSign").checked = isSigner;

    document.getElementById("role-hint").innerHTML = SIGNING_ROLE_HINTS[role] || "";
}

function toggleOrganizationFields() {
    const show = document.getElementById("partyType").value === "ORGANIZATION";

    document.getElementById("organizationFields").classList.toggle("hidden", !show);
}

function resetModal() {
    [
        "partyName",
        "partyMobile",
        "partyPhone",
        "partyEmail",
        "nationalId",
        "nationality",
        "addressCountry",
        "addressCity",
        "organizationName",
        "commercialRegistration",
        "taxNumber",
        "invitationMessage",
    ].forEach((id) => {
        const element = document.getElementById(id);

        if (element) {
            element.value = "";
        }
    });

    document.getElementById("partyTitle").value = "السيد";
    document.getElementById("partyType").value = "INDIVIDUAL";
    document.getElementById("signingRole").value = "SIGNER";

    applyRoleDefaults("SIGNER");
    toggleOrganizationFields();
}

function fillModal(party) {
    document.getElementById("partyTitle").value = party.title || "السيد";
    document.getElementById("partyName").value = party.full_name || "";
    document.getElementById("partyMobile").value = party.mobile || "";
    document.getElementById("partyPhone").value = party.phone || "";
    document.getElementById("partyEmail").value = party.email || "";

    document.getElementById("partyType").value = party.party_type || "INDIVIDUAL";
    document.getElementById("signingRole").value = party.signing_role || "SIGNER";

    document.getElementById("nationalId").value = party.national_id || "";
    document.getElementById("nationality").value = party.nationality || "";
    document.getElementById("addressCountry").value = party.address_country || "";
    document.getElementById("addressCity").value = party.address_city || "";

    document.getElementById("organizationName").value = party.organization_name || "";
    document.getElementById("commercialRegistration").value =
        party.commercial_registration || "";
    document.getElementById("taxNumber").value = party.tax_number || "";

    document.getElementById("invitationMessage").value =
        party.invitation_message || "";

    document.getElementById("canViewContract").checked =
        Boolean(party.can_view_contract);
    document.getElementById("canComment").checked =
        Boolean(party.can_comment);
    document.getElementById("canEdit").checked =
        Boolean(party.can_edit);
    document.getElementById("canUploadFiles").checked =
        Boolean(party.can_upload_files);
    document.getElementById("canSign").checked =
        Boolean(party.can_sign);

    document.getElementById("role-hint").innerHTML =
        SIGNING_ROLE_HINTS[party.signing_role] || "";

    toggleOrganizationFields();
}

function getModalData() {
    return {
        title: document.getElementById("partyTitle").value,
        full_name: document.getElementById("partyName").value.trim(),
        mobile: document.getElementById("partyMobile").value.trim(),
        phone: document.getElementById("partyPhone").value.trim(),
        email: document.getElementById("partyEmail").value.trim(),

        party_type: document.getElementById("partyType").value,
        signing_role: document.getElementById("signingRole").value,

        national_id: document.getElementById("nationalId").value.trim(),
        nationality: document.getElementById("nationality").value.trim(),
        address_country: document.getElementById("addressCountry").value.trim(),
        address_city: document.getElementById("addressCity").value.trim(),

        organization_name: document.getElementById("organizationName").value.trim(),
        commercial_registration:
            document.getElementById("commercialRegistration").value.trim(),
        tax_number: document.getElementById("taxNumber").value.trim(),

        can_view_contract:
            document.getElementById("canViewContract").checked,
        can_comment:
            document.getElementById("canComment").checked,
        can_edit:
            document.getElementById("canEdit").checked,
        can_upload_files:
            document.getElementById("canUploadFiles").checked,
        can_sign:
            document.getElementById("canSign").checked,

        invitation_message:
            document.getElementById("invitationMessage").value.trim(),

        signing_order:
            editingIndex !== null
                ? parties[editingIndex].signing_order
                : parties.length + 1,
    };
}

function validateParty(data) {
    if (!data.full_name) {
        return "اسم الطرف مطلوب.";
    }

    if (!data.mobile) {
        return "رقم الجوال مطلوب.";
    }

    if (!/^\+?[0-9\-]{7,15}$/.test(data.mobile.replace(/\s/g, ""))) {
        return "رقم الجوال غير صحيح — أدخل الرقم مع رمز الدولة مثال: +966512345678";
    }

    if (!data.email) {
        return "البريد الإلكتروني مطلوب لإرسال الدعوة.";
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
        return "صيغة البريد الإلكتروني غير صحيحة.";
    }

    if (data.party_type === "INDIVIDUAL" && !data.national_id) {
        return "رقم الهوية / الإقامة مطلوب إذا كان الطرف فرداً.";
    }

    if (data.party_type === "ORGANIZATION") {
        if (!data.organization_name) {
            return "اسم المنشأة مطلوب.";
        }

        if (!data.commercial_registration) {
            return "رقم السجل التجاري مطلوب.";
        }
    }

    if (["SIGNER", "DELEGATED"].includes(data.signing_role) && !data.can_sign) {
        return "الموقّع أو المفوّض يجب تفعيل صلاحية التوقيع.";
    }

    const duplicatedMobile = parties.some((party, index) => {
        return party.mobile === data.mobile && index !== editingIndex;
    });

    if (duplicatedMobile) {
        return "رقم الجوال مضاف مسبقاً.";
    }

    const duplicatedEmail = parties.some((party, index) => {
        return party.email === data.email && index !== editingIndex;
    });

    if (duplicatedEmail) {
        return "البريد الإلكتروني مضاف مسبقاً.";
    }

    return "";
}

function savePartyData() {
    const data = getModalData();
    const error = validateParty(data);

    if (error) {
        document.getElementById("parties-error").textContent = error;
        return;
    }

    if (editingIndex === null) {
        parties.push(data);
    } else {
        parties[editingIndex] = data;
    }

    renderParties();
    closePartyModal();
}

function removeParty(index) {
    parties.splice(index, 1);

    parties = parties.map((party, partyIndex) => {
        return {
            ...party,
            signing_order: partyIndex + 1,
        };
    });

    renderParties();
}

function renderParties() {
    const empty = document.getElementById("parties-empty");
    const list = document.getElementById("parties-list");

    empty.style.display = parties.length === 0 ? "block" : "none";

    list.innerHTML = parties
        .map((party, index) => {
            return `
                <div class="party-row">
                    <div class="party-label blue">
                        ${getLegalTitle(index)}
                    </div>

                    <div class="party-main-info">
                        <div class="avatar formal">
                            <span>${getInitials(party.full_name)}</span>
                        </div>

                        <div class="party-details">
                            <div class="name-row">
                                <h4>${esc(party.title || "")} ${esc(party.full_name)}</h4>
                            </div>

                            <p class="party-type-label">
                                ${PARTY_TYPE_LABELS[party.party_type] || "فرد"} ·
                                ${SIGNING_ROLE_LABELS[party.signing_role] || ""}
                            </p>

                            <div class="party-meta">
                                ${
                                    party.national_id
                                        ? `<span class="meta-item">هوية: ${esc(party.national_id)}</span>`
                                        : ""
                                }

                                ${
                                    party.nationality
                                        ? `<span class="meta-item">الجنسية: ${esc(party.nationality)}</span>`
                                        : ""
                                }

                                ${
                                    party.organization_name
                                        ? `<span class="meta-item">المنشأة: ${esc(party.organization_name)}</span>`
                                        : ""
                                }

                                ${
                                    party.address_country
                                        ? `<span class="meta-item">📍 ${esc(party.address_country)}${
                                              party.address_city
                                                  ? `، ${esc(party.address_city)}`
                                                  : ""
                                          }</span>`
                                        : ""
                                }
                            </div>
                        </div>
                    </div>

                    <div class="contact-info-col">
                        <h5>معلومات التواصل</h5>

                        <div class="contact-item">
                            <span class="mini-label">الجوال</span>
                            <span dir="ltr">${esc(party.mobile)}</span>
                        </div>

                        <div class="contact-item">
                            <span class="mini-label">البريد</span>
                            <span>${esc(party.email)}</span>
                        </div>
                    </div>

                    <div class="role-col">
                        <h5>الصلاحيات</h5>

                        <div class="permissions">
                            ${getPermLabels(party)
                                .map((label) => `<span>${label}</span>`)
                                .join("")}
                        </div>

                        <div class="row-actions">
                            <button
                                class="small-btn"
                                data-action="edit"
                                data-index="${index}"
                            >
                                تعديل
                            </button>

                            <button
                                class="small-btn danger"
                                data-action="delete"
                                data-index="${index}"
                            >
                                حذف
                            </button>
                        </div>
                    </div>
                </div>
            `;
        })
        .join("");
}
function renderReview() {
    const titleAr = document.getElementById("title_ar").value.trim();
    const titleEn = document.getElementById("title_en").value.trim();
    const desc = document.getElementById("description_ar").value.trim();
    const clauses = getClauses();

    const contractTypeLabels = {
        SERVICES: "عقد خدمات",
        SUPPLY: "عقد توريد",
        RENT: "عقد إيجار",
        PARTNERSHIP: "عقد شراكة",
        CONSULTING: "عقد استشاري",
        EMPLOYMENT: "عقد عمل",
        OTHER: "أخرى",
    };

    const paymentLabels = {
        UPFRONT: "دفعة مقدمة كاملة",
        INSTALLMENTS: "دفعات مرحلية",
        ON_DELIVERY: "عند التسليم",
        CUSTOM: "مخصصة حسب البنود",
    };

    const contractType = document.getElementById("contract_type").value || "";
    const contractValue = document.getElementById("contract_value").value || "";
    const currency = document.getElementById("currency").value || "";
    const paymentMethod = document.getElementById("payment_method").value || "";
    const startDate = document.getElementById("start_date").value || "";
    const endDate = document.getElementById("end_date").value || "";
    const location = document.getElementById("execution_location").value.trim() || "";

    document.getElementById("review-summary").innerHTML = [
        ["اسم العقد", titleAr || "—"],
        ["نوع العقد", contractTypeLabels[contractType] || "—"],
        [
            "المدة الزمنية",
            durationType === "open"
                ? "غير محددة"
                : startDate && endDate
                ? `${startDate} → ${endDate}`
                : "—",
        ],
        ["قيمة العقد", contractValue ? `${contractValue} ${currency}` : "—"],
        ["طريقة الدفع", paymentLabels[paymentMethod] || "—"],
        ["مكان التنفيذ", location || "—"],
        ["عدد الأطراف", parties.length + 1],
        ["عدد البنود", clauses.length],
        ["الحالة", "مسودة — بانتظار الإنشاء"],
    ]
        .map(
            ([label, value]) => `
                <div class="summary-item">
                    <span>${label}</span>
                    <strong>${esc(String(value))}</strong>
                </div>
            `
        )
        .join("");

    document.getElementById("review-parties-list").innerHTML = parties.length
        ? parties
              .map(
                  (party, index) => `
                    <div class="party-row-review">
                        <div class="party-identity">
                            <div class="party-avatar-sm">
                                ${getInitials(party.full_name)}
                            </div>

                            <div>
                                <h4>
                                    ${esc(party.title || "")} ${esc(party.full_name)}
                                    <span>— ${getLegalTitle(index)}</span>
                                </h4>

                                <p>${PARTY_TYPE_LABELS[party.party_type] || ""}</p>
                                <p>${SIGNING_ROLE_LABELS[party.signing_role] || ""}</p>
                                <span dir="ltr">${esc(party.mobile)}</span>
                            </div>
                        </div>

                        <div class="permission-tags">
                            ${getPermLabels(party)
                                .map((label) => `<span>${label}</span>`)
                                .join("")}
                        </div>
                    </div>
                `
              )
              .join("")
        : '<div class="empty-state">لا توجد أطراف مضافة</div>';

    const timelineCard = document.getElementById("review-timeline-card");

    if (parties.length > 1) {
        timelineCard.style.display = "block";

        document.getElementById("review-timeline").innerHTML = parties
            .map(
                (party, index) => `
                    <div class="timeline-item">
                        <div class="timeline-num">${index + 2}</div>

                        <div>
                            <strong>${esc(party.title || "")} ${esc(party.full_name)}</strong>
                            <span>${getLegalTitle(index)} · ${
                    SIGNING_ROLE_LABELS[party.signing_role] || ""
                }</span>
                        </div>
                    </div>
                `
            )
            .join("");
    } else {
        timelineCard.style.display = "none";
    }

    document.getElementById("review-sms").innerHTML = parties
        .map(
            (party) => `
                <div class="sms-item">
                    <div class="sms-head">
                        <strong>${esc(party.title || "")} ${esc(party.full_name)}</strong>
                        <span>${esc(party.email)}</span>
                    </div>

                    <p>
                        منصة ميثاق: لديك طلب توقيع على عقد "${esc(titleAr)}".
                        يرجى تسجيل الدخول للمراجعة والتوقيع.
                        ${
                            party.invitation_message
                                ? `<br>${esc(party.invitation_message)}`
                                : ""
                        }
                    </p>
                </div>
            `
        )
        .join("");

    renderContractDocument({
        titleAr,
        titleEn,
        desc,
        clauses,
        contractValue,
        currency,
        paymentMethod,
        paymentLabels,
    });

    document.getElementById("final-checklist").innerHTML = [
        "تم التحقق من بيانات العقد",
        `تم إضافة ${parties.length} طرف للعقد`,
        `تم إدخال ${clauses.length} بند للعقد`,
        "العقد جاهز لإرسال طلبات التوقيع",
    ]
        .map((text) => `<li>${text}</li>`)
        .join("");
}

function renderContractDocument(data) {
    const {
        titleAr,
        titleEn,
        desc,
        clauses,
        contractValue,
        currency,
        paymentMethod,
        paymentLabels,
    } = data;

    const now = new Date();
    const dayNames = [
        "الأحد",
        "الاثنين",
        "الثلاثاء",
        "الأربعاء",
        "الخميس",
        "الجمعة",
        "السبت",
    ];

    const dayName = dayNames[now.getDay()];
    const miladi = now.toLocaleDateString("ar-SA", {
        day: "numeric",
        month: "long",
        year: "numeric",
    });

    const arabicNums = [
        "",
        "الأولى",
        "الثانية",
        "الثالثة",
        "الرابعة",
        "الخامسة",
        "السادسة",
        "الثامنة",
        "التاسعة",
        "العاشرة",
        "الحادية عشرة",
        "الثانية عشرة",
    ];

    let articleIndex = 1;
    const articles = [];

    const obligationClauses = clauses.filter((clause) => clause.section === "obligations");
    const penaltyClauses = clauses.filter((clause) => clause.section === "penalties");
    const terminationClauses = clauses.filter(
        (clause) => clause.section === "termination"
    );

    const sharedClauses = obligationClauses.filter(
        (clause) => !clause.assigned_party || clause.assigned_party === ""
    );

    const party1Clauses = obligationClauses.filter(
        (clause) => clause.assigned_party === "PARTY_1"
    );

    const otherPartyClauses = {};

    obligationClauses
        .filter(
            (clause) =>
                clause.assigned_party &&
                clause.assigned_party !== "PARTY_1" &&
                clause.assigned_party !== ""
        )
        .forEach((clause) => {
            if (!otherPartyClauses[clause.assigned_party]) {
                otherPartyClauses[clause.assigned_party] = [];
            }

            otherPartyClauses[clause.assigned_party].push(clause);
        });

    const paymentClauses = obligationClauses.filter(
        (clause) =>
            clause.clause_type === "PAYMENT" || clause.clause_type === "DELIVERY"
    );

    articles.push(`
        <div class="contract-article">
            <h4>المادة ${arabicNums[articleIndex]}: موضوع العقد</h4>
            <p>
                يُعنى هذا العقد بتنظيم العلاقة بين الأطراف فيما يخص
                <strong>"${esc(titleAr)}"</strong>
                ${desc ? `، ويشمل: ${esc(desc)}` : ""}.
            </p>
        </div>
    `);
    articleIndex++;

    if (sharedClauses.length > 0) {
        articles.push(`
            <div class="contract-article">
                <h4>المادة ${arabicNums[articleIndex]}: التزامات الطرفين معاً</h4>
                <p>يلتزم جميع الأطراف بكل مما يلي:</p>
                <ol class="contract-clauses-list">
                    ${sharedClauses.map((clause) => `<li>${esc(clause.content_ar)}</li>`).join("")}
                </ol>
            </div>
        `);
        articleIndex++;
    }

    if (party1Clauses.length > 0) {
        articles.push(`
            <div class="contract-article">
                <h4>المادة ${arabicNums[articleIndex]}: التزامات الطرف الأول</h4>
                <ol class="contract-clauses-list">
                    ${party1Clauses.map((clause) => `<li>${esc(clause.content_ar)}</li>`).join("")}
                </ol>
            </div>
        `);
        articleIndex++;
    }

    Object.entries(otherPartyClauses).forEach(([key, partyClauses]) => {
        const index = parseInt(key.replace("PARTY_", ""), 10) - 2;
        const label = parties[index] ? getLegalTitle(index) : key;

        articles.push(`
            <div class="contract-article">
                <h4>المادة ${arabicNums[articleIndex]}: التزامات ${label}</h4>
                <ol class="contract-clauses-list">
                    ${partyClauses.map((clause) => `<li>${esc(clause.content_ar)}</li>`).join("")}
                </ol>
            </div>
        `);

        articleIndex++;
    });

    if (contractValue || paymentClauses.length > 0) {
        articles.push(`
            <div class="contract-article">
                <h4>المادة ${arabicNums[articleIndex]}: المقابل المالي وآلية الدفع</h4>

                ${
                    contractValue
                        ? `<p>
                            اتفق الطرفان على أن إجمالي قيمة العقد هي
                            <strong>${esc(contractValue)} ${esc(currency)}</strong>
                            وتُسدّد وفق الآلية التالية:
                            ${paymentLabels[paymentMethod] || ""}.
                        </p>`
                        : ""
                }

                ${
                    paymentClauses.length > 0
                        ? `<ol class="contract-clauses-list">
                            ${paymentClauses
                                .map((clause) => `<li>${esc(clause.content_ar)}</li>`)
                                .join("")}
                        </ol>`
                        : ""
                }
            </div>
        `);

        articleIndex++;
    }

    if (penaltyClauses.length > 0) {
        articles.push(`
            <div class="contract-article">
                <h4>المادة ${arabicNums[articleIndex]}: الشروط الجزائية والتعويضات</h4>
                <ol class="contract-clauses-list">
                    ${penaltyClauses.map((clause) => `<li>${esc(clause.content_ar)}</li>`).join("")}
                </ol>
            </div>
        `);

        articleIndex++;
    }

    articles.push(`
        <div class="contract-article">
            <h4>المادة ${arabicNums[articleIndex]}: حالات الإنهاء والفسخ</h4>
            <p>
                يحق لأي من الأطراف إنهاء العقد في حال إخلال الطرف الآخر بأي بند من بنوده،
                بعد توجيه إشعار خطي عبر منصة <strong>ميثاق</strong> بمهلة لا تقل عن سبعة أيام.
            </p>

            ${
                terminationClauses.length > 0
                    ? `<ol class="contract-clauses-list">
                        ${terminationClauses
                            .map((clause) => `<li>${esc(clause.content_ar)}</li>`)
                            .join("")}
                    </ol>`
                    : ""
            }
        </div>
    `);
    articleIndex++;

    articles.push(`
        <div class="contract-article">
            <h4>المادة ${arabicNums[articleIndex]}: السرية والملكية الفكرية</h4>
            <p>
                يلتزم جميع الأطراف بالمحافظة على سرية كافة المعلومات والبيانات
                التي يطلعون عليها بموجب هذا العقد.
            </p>
        </div>
    `);
    articleIndex++;

    articles.push(`
        <div class="contract-article">
            <h4>المادة ${arabicNums[articleIndex]}: القانون الواجب التطبيق وفض النزاعات</h4>
            <p>
                يخضع هذا العقد للأنظمة واللوائح المعمول بها في المملكة العربية السعودية.
            </p>
        </div>
    `);
    articleIndex++;

    articles.push(`
        <div class="contract-article">
            <h4>المادة ${arabicNums[articleIndex]}: النسخ والتوقيع</h4>
            <p>
                أُبرم هذا العقد إلكترونياً عبر منصة <strong>ميثاق</strong>،
                ويُعدّ التوقيع الرقمي عليه بمثابة موافقة نهائية وملزمة لجميع الأطراف.
            </p>
        </div>
    `);

    document.getElementById("review-doc").innerHTML = `
        <div class="contract-doc" dir="rtl">
            <div class="contract-title-block">
                <h2>${esc(titleAr)}</h2>
                <p class="contract-bismillah">بسم الله الرحمن الرحيم</p>
                ${titleEn ? `<p class="contract-title-en">${esc(titleEn)}</p>` : ""}
            </div>

            <div class="contract-preamble">
                تم بعون الله وتوفيقه في يوم
                (<strong>${dayName}</strong>) الموافق <strong>${miladi}</strong>،
                تحرير هذا العقد بين كل من:
                <br><br>
                <strong>الطرف الأول:</strong>
                منشئ العقد، والمُشار إليه في هذا العقد بـ "الطرف الأول"

                ${parties
                    .map((party, index) => {
                        const legalRef = `"${getLegalTitle(index)}"`;

                        if (party.party_type === "ORGANIZATION") {
                            return `
                                <br><br>
                                <strong>${getLegalTitle(index)}:</strong>
                                منشأة <strong>${esc(party.organization_name)}</strong>
                                ${
                                    party.commercial_registration
                                        ? `، السجل التجاري رقم (${esc(
                                              party.commercial_registration
                                          )})`
                                        : ""
                                }
                                ${
                                    party.tax_number
                                        ? `، الرقم الضريبي (${esc(party.tax_number)})`
                                        : ""
                                }
                                ، يمثلها في هذا العقد ${esc(party.title || "")}
                                ${esc(party.full_name)}
                                ${
                                    party.national_id
                                        ? `، صاحب/ة الهوية رقم (${esc(
                                              party.national_id
                                          )})`
                                        : ""
                                }
                                ، والمُشار إليها في هذا العقد بـ ${legalRef}
                            `;
                        }

                        return `
                            <br><br>
                            <strong>${getLegalTitle(index)}:</strong>
                            ${esc(party.title || "")} ${esc(party.full_name)}
                            ${
                                party.national_id
                                    ? `، صاحب/ة الهوية أو الإقامة رقم (${esc(
                                          party.national_id
                                      )})`
                                    : ""
                            }
                            ، والمُشار إليه في هذا العقد بـ ${legalRef}
                        `;
                    })
                    .join("")}
            </div>

            <div class="contract-preamble contract-intro">
                <strong>تمهيد:</strong><br>
                بما أن الطرف الأول يرغب في إبرام هذا العقد المتعلق بـ
                <strong>"${esc(titleAr)}"</strong>
                ${desc ? `والذي يهدف إلى: ${esc(desc)}،` : ""}
                وبما أن الأطراف لديهم الأهلية الكاملة والرغبة الصادقة في الالتزام،
                فقد اتفق الطرفان على ما يلي:
            </div>

            ${articles.join("")}

            <div class="contract-signatures">
                <div class="sig-block">
                    <p class="sig-label">توقيع الطرف الأول</p>
                    <div class="sig-line"></div>
                    <p class="sig-name">المنشئ</p>
                </div>

                ${parties
                    .map(
                        (party, index) => `
                            <div class="sig-block">
                                <p class="sig-label">توقيع ${getLegalTitle(index)}</p>
                                <div class="sig-line"></div>
                                <p class="sig-name">
                                    ${esc(party.title || "")} ${esc(party.full_name)}
                                </p>
                            </div>
                        `
                    )
                    .join("")}
            </div>
        </div>
    `;
}

async function submitContract() {
    const button = document.getElementById("submit-btn");

    button.disabled = true;
    button.textContent = "جاري الإنشاء...";

    try {
        const response = await fetch("/api/contracts/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                title_ar: document.getElementById("title_ar").value.trim(),
                title_en: document.getElementById("title_en").value.trim(),
                description_ar: document.getElementById("description_ar").value.trim(),
                contract_type: document.getElementById("contract_type").value,
                duration_type: durationType,
                start_date:
                    durationType === "fixed"
                        ? document.getElementById("start_date").value
                        : null,
                end_date:
                    durationType === "fixed"
                        ? document.getElementById("end_date").value
                        : null,
                contract_value:
                    document.getElementById("contract_value").value || null,
                currency: document.getElementById("currency").value,
                payment_method: document.getElementById("payment_method").value,
                execution_location:
                    document.getElementById("execution_location").value.trim(),
                clauses: getClauses(),
                invite_parties: parties,
                final_notes: document.getElementById("final-notes").value.trim(),
                contract_html: document.getElementById("review-doc").innerHTML,
            }),
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = `/invitations/my-contracts/${data.invitation_id}/`;
        } else {
            alert("خطأ: " + JSON.stringify(data));
            button.disabled = false;
            button.textContent = "إنشاء العقد وإرسال طلبات التوقيع";
        }
    } catch (error) {
        alert("خطأ في الاتصال");
        button.disabled = false;
        button.textContent = "إنشاء العقد وإرسال طلبات التوقيع";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("closeModal")?.addEventListener("click", closePartyModal);
    document.getElementById("cancelParty")?.addEventListener("click", closePartyModal);
    document.getElementById("saveParty")?.addEventListener("click", savePartyData);

    document
        .getElementById("partyType")
        ?.addEventListener("change", toggleOrganizationFields);

    document.getElementById("signingRole")?.addEventListener("change", function () {
        applyRoleDefaults(this.value);
    });

    document.getElementById("partyModal")?.addEventListener("click", function (event) {
        if (event.target === this) {
            closePartyModal();
        }
    });

    document.getElementById("parties-list")?.addEventListener("click", function (event) {
        const button = event.target.closest("button");

        if (!button) return;

        const index = Number(button.dataset.index);

        if (button.dataset.action === "edit") {
            openPartyModal(index);
        }

        if (button.dataset.action === "delete") {
            removeParty(index);
        }
    });

    toggleOrganizationFields();
    applyRoleDefaults("SIGNER");
    renderParties();
    addClause("obligations");
});