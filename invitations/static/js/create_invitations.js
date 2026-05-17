let parties = [];
let editingIndex = null;

const partyForm = document.getElementById("partyForm");
const partiesPayload = document.getElementById("partiesPayload");
const dynamicParties = document.getElementById("dynamicParties");
const emptyState = document.getElementById("emptyState");
const formError = document.getElementById("formError");

const partyModal = document.getElementById("partyModal");
const addPartyBtn = document.getElementById("addPartyBtn");
const closeModal = document.getElementById("closeModal");
const cancelParty = document.getElementById("cancelParty");
const saveParty = document.getElementById("saveParty");
const modalTitle = document.getElementById("modalTitle");

const partyName = document.getElementById("partyName");
const partyMobile = document.getElementById("partyMobile");
const partyEmail = document.getElementById("partyEmail");

const partyType = document.getElementById("partyType");
const contractRole = document.getElementById("contractRole");
const signingRole = document.getElementById("signingRole");

const nationalId = document.getElementById("nationalId");
const nationality = document.getElementById("nationality");

const organizationName = document.getElementById("organizationName");
const commercialRegistration = document.getElementById("commercialRegistration");
const taxNumber = document.getElementById("taxNumber");

const signingOrder = document.getElementById("signingOrder");
const invitationMessage = document.getElementById("invitationMessage");

const canViewContract = document.getElementById("canViewContract");
const canComment = document.getElementById("canComment");
const canEdit = document.getElementById("canEdit");
const canUploadFiles = document.getElementById("canUploadFiles");
const canSign = document.getElementById("canSign");

const organizationFields = document.getElementById("organizationFields");

const partyTypeLabels = {
  INDIVIDUAL: "فرد",
  ORGANIZATION: "منشأة"
};

const contractRoleLabels = {
  FIRST_PARTY: "الطرف الأول",
  SECOND_PARTY: "الطرف الثاني",
  WITNESS: "شاهد"
};

const signingRoleLabels = {
  SIGNER: "موقّع",
  REVIEWER: "مراجع",
  APPROVER: "معتمد"
};

function getPermissions(data) {
  const permissions = [];

  if (data.can_view_contract) permissions.push("عرض العقد");
  if (data.can_comment) permissions.push("إضافة ملاحظات");
  if (data.can_edit) permissions.push("تعديل");
  if (data.can_upload_files) permissions.push("رفع مرفقات");
  if (data.can_sign) permissions.push("التوقيع");

  return permissions;
}

function toggleOrganizationFields() {
  if (!organizationFields || !partyType) return;

  if (partyType.value === "ORGANIZATION") {
    organizationFields.classList.remove("hidden");
  } else {
    organizationFields.classList.add("hidden");
  }
}

function resetModal() {
  partyName.value = "";
  partyMobile.value = "";
  partyEmail.value = "";

  partyType.value = "INDIVIDUAL";
  contractRole.value = "SECOND_PARTY";
  signingRole.value = "SIGNER";

  nationalId.value = "";
  nationality.value = "";

  organizationName.value = "";
  commercialRegistration.value = "";
  taxNumber.value = "";

  signingOrder.value = parties.length + 1;
  invitationMessage.value = "";

  canViewContract.checked = true;
  canComment.checked = false;
  canEdit.checked = false;
  canUploadFiles.checked = false;
  canSign.checked = true;

  toggleOrganizationFields();
}

function fillModal(party) {
  partyName.value = party.full_name || "";
  partyMobile.value = party.mobile || "";
  partyEmail.value = party.email || "";

  partyType.value = party.party_type || "INDIVIDUAL";
  contractRole.value = party.contract_role || "SECOND_PARTY";
  signingRole.value = party.signing_role || "SIGNER";

  nationalId.value = party.national_id || "";
  nationality.value = party.nationality || "";

  organizationName.value = party.organization_name || "";
  commercialRegistration.value = party.commercial_registration || "";
  taxNumber.value = party.tax_number || "";

  signingOrder.value = party.signing_order || parties.length + 1;
  invitationMessage.value = party.invitation_message || "";

  canViewContract.checked = Boolean(party.can_view_contract);
  canComment.checked = Boolean(party.can_comment);
  canEdit.checked = Boolean(party.can_edit);
  canUploadFiles.checked = Boolean(party.can_upload_files);
  canSign.checked = Boolean(party.can_sign);

  toggleOrganizationFields();
}

function openModal(index = null) {
  editingIndex = index;
  formError.textContent = "";

  if (index === null) {
    modalTitle.textContent = "إضافة طرف مطلوب توقيعه";
    resetModal();
  } else {
    modalTitle.textContent = "تعديل بيانات الطرف";
    fillModal(parties[index]);
  }

  partyModal.classList.add("show");
  partyModal.setAttribute("aria-hidden", "false");
}

function closePartyModal() {
  partyModal.classList.remove("show");
  partyModal.setAttribute("aria-hidden", "true");
}

function getModalData() {
  return {
    full_name: partyName.value.trim(),
    mobile: partyMobile.value.trim(),
    email: partyEmail.value.trim(),

    party_type: partyType.value,
    contract_role: contractRole.value,
    signing_role: signingRole.value,

    national_id: nationalId.value.trim(),
    nationality: nationality.value.trim(),

    organization_name: organizationName.value.trim(),
    commercial_registration: commercialRegistration.value.trim(),
    tax_number: taxNumber.value.trim(),

    can_view_contract: canViewContract.checked,
    can_comment: canComment.checked,
    can_edit: canEdit.checked,
    can_upload_files: canUploadFiles.checked,
    can_sign: canSign.checked,

    signing_order: Number(signingOrder.value || parties.length + 1),
    invitation_message: invitationMessage.value.trim()
  };
}

function validateParty(data) {
  if (!data.full_name) return "اسم الطرف مطلوب.";
  if (!data.mobile) return "رقم الجوال مطلوب.";

  const saMobilePattern = /^(\+9665|05)[0-9]{8}$/;
  if (!saMobilePattern.test(data.mobile)) {
    return "صيغة رقم الجوال غير صحيحة. استخدمي 05xxxxxxxx أو +9665xxxxxxxx.";
  }

  if (data.party_type === "INDIVIDUAL" && !data.national_id) {
    return "رقم الهوية مطلوب إذا كان الطرف فردًا.";
  }

  if (data.party_type === "ORGANIZATION") {
    if (!data.organization_name) return "اسم المنشأة مطلوب.";
    if (!data.commercial_registration) return "رقم السجل التجاري مطلوب.";
  }

  if (!data.can_view_contract) {
    return "لا يمكن إرسال دعوة لطرف بدون صلاحية عرض العقد.";
  }

  if (data.signing_role === "SIGNER" && !data.can_sign) {
    return "إذا كان دور الطرف موقّع، يجب تفعيل صلاحية التوقيع.";
  }

  const duplicate = parties.some((party, index) => {
    return party.mobile === data.mobile && index !== editingIndex;
  });

  if (duplicate) return "رقم الجوال مضاف مسبقًا.";

  return "";
}

function savePartyData() {
  const data = getModalData();
  const error = validateParty(data);

  if (error) {
    formError.textContent = error;
    return;
  }

  if (editingIndex === null) {
    parties.push(data);
  } else {
    parties[editingIndex] = data;
  }

  normalizeSigningOrders();
  renderParties();
  closePartyModal();
}

function removeParty(index) {
  parties.splice(index, 1);
  normalizeSigningOrders();
  renderParties();
}

function normalizeSigningOrders() {
  parties = parties
    .map((party, index) => ({
      ...party,
      signing_order: Number(party.signing_order || index + 1)
    }))
    .sort((a, b) => a.signing_order - b.signing_order);
}

function renderParties() {
  dynamicParties.innerHTML = "";

  emptyState.style.display = parties.length === 0 ? "block" : "none";

  parties.forEach((party, index) => {
    const row = document.createElement("div");
    row.className = "party-row";

    const permissions = getPermissions(party);

    row.innerHTML = `
      <div class="party-label blue">الطرف ${index + 2}</div>

      <div class="party-main-info">
        <div class="avatar formal">
          <span>${getInitials(party.full_name)}</span>
        </div>

        <div class="party-details">
          <div class="name-row">
            <h4>${escapeHtml(party.full_name)}</h4>
          </div>

          <p class="party-type-label">${partyTypeLabels[party.party_type] || "طرف"} ·
            ${contractRoleLabels[party.contract_role] || "دور قانوني"} ·
            ${signingRoleLabels[party.signing_role] || "دور توقيع"}
          </p>

          <div class="party-meta">
            ${party.national_id ? `<span class="meta-item">رقم الهوية: ${escapeHtml(party.national_id)}</span>` : ""}
            ${party.nationality ? `<span class="meta-item">الجنسية: ${escapeHtml(party.nationality)}</span> `: ""}
            ${party.organization_name ? `<span class="meta-item">المنشأة: ${escapeHtml(party.organization_name)}</span> `: ""}
            ${party.commercial_registration ? `<span class="meta-item">السجل التجاري: ${escapeHtml(party.commercial_registration)}</span>` : ""}
            <span class="meta-item">ترتيب التوقيع: ${escapeHtml(party.signing_order)}</span>
          </div>
        </div>
      </div>

      <div class="contact-info-col">
        <h5>معلومات التواصل</h5>

        <div class="contact-item">
          <span class="mini-label">الجوال</span>
          <span>${escapeHtml(party.mobile)}</span>
        </div>

        <div class="contact-item">
          <span class="mini-label">البريد</span>
          <span>${party.email ? escapeHtml(party.email) : "غير مضاف"}</span>
        </div>
      </div>

      <div class="role-col">
        <h5>الصلاحيات</h5>

        <div class="permissions">
          ${permissions.map(permission => `<span>${permission}</span>`).join("")}
        </div>

        <div class="row-actions">
          <button type="button" class="small-btn" data-action="edit" data-index="${index}">تعديل</button>
          <button type="button" class="small-btn danger" data-action="delete" data-index="${index}">حذف</button>
        </div>
      </div>
    `;

    dynamicParties.appendChild(row);
  });

  partiesPayload.value = JSON.stringify(parties);
}

function getInitials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map(word => word[0])
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

addPartyBtn.addEventListener("click", () => openModal());
closeModal.addEventListener("click", closePartyModal);
cancelParty.addEventListener("click", closePartyModal);
saveParty.addEventListener("click", savePartyData);

partyType.addEventListener("change", toggleOrganizationFields);

partyModal.addEventListener("click", event => {
  if (event.target === partyModal) closePartyModal();
});

dynamicParties.addEventListener("click", event => {
  const button = event.target.closest("button");
  if (!button) return;

  const index = Number(button.dataset.index);

  if (button.dataset.action === "edit") {
    openModal(index);
  }

  if (button.dataset.action === "delete") {
    removeParty(index);
  }
});

partyForm.addEventListener("submit", event => {
  formError.textContent = "";

  if (parties.length < 1) {
    event.preventDefault();
    formError.textContent = "يجب إضافة طرف واحد على الأقل قبل المتابعة.";
    return;
  }

  partiesPayload.value = JSON.stringify(parties);
});

toggleOrganizationFields();
renderParties();