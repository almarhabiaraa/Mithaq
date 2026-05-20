const newInvitationModal = document.getElementById('newInvitationModal');
const openNewInvitationModal = document.getElementById('openNewInvitationModal');
const closeNewInvitationModal = document.getElementById('closeNewInvitationModal');
const cancelNewInvitation = document.getElementById('cancelNewInvitation');

const newPartyType = document.getElementById('newPartyType');
const newSigningRole = document.getElementById('newSigningRole');
const newOrganizationFields = document.getElementById('newOrganizationFields');
const newRoleHint = document.getElementById('newRoleHint');

const NEW_ROLE_HINTS = {
    SIGNER:
        '<strong>موقّع:</strong> طرف ملزَم قانونياً يحق له الاطلاع على العقد والتوقيع عليه.',

    APPROVER:
        '<strong>معتمد:</strong> يراجع العقد ويعتمده حسب الصلاحيات الممنوحة له.',

    REVIEWER:
        '<strong>مراجع:</strong> يطّلع على العقد ويضيف ملاحظاته فقط بدون توقيع.',
};

function openNewModal() {
    if (!newInvitationModal) return;

    newInvitationModal.classList.add('show');
    newInvitationModal.setAttribute('aria-hidden', 'false');

    document.body.style.overflow = 'hidden';
}

function closeNewModal() {
    if (!newInvitationModal) return;

    newInvitationModal.classList.remove('show');
    newInvitationModal.setAttribute('aria-hidden', 'true');

    document.body.style.overflow = '';
}

function toggleNewOrganizationFields() {
    if (!newPartyType || !newOrganizationFields) return;

    const isOrganization =
        newPartyType.value === 'ORGANIZATION';

    newOrganizationFields.classList.toggle(
        'hidden',
        !isOrganization
    );
}

function applyNewRoleDefaults() {
    if (!newSigningRole) return;

    const role = newSigningRole.value;

    const canSign = document.getElementById('newCanSign');
    const canComment = document.getElementById('newCanComment');
    const canEdit = document.getElementById('newCanEdit');

    if (canSign) {
        canSign.checked = role !== 'REVIEWER';
    }

    if (canComment) {
        canComment.checked = true;
    }

    if (canEdit) {
        canEdit.checked = false;
    }

    if (newRoleHint) {
        newRoleHint.innerHTML =
            NEW_ROLE_HINTS[role] || '';
    }
}

openNewInvitationModal?.addEventListener(
    'click',
    openNewModal
);

closeNewInvitationModal?.addEventListener(
    'click',
    closeNewModal
);

cancelNewInvitation?.addEventListener(
    'click',
    closeNewModal
);

newInvitationModal?.addEventListener(
    'click',
    function (e) {
        if (e.target === newInvitationModal) {
            closeNewModal();
        }
    }
);

newPartyType?.addEventListener(
    'change',
    toggleNewOrganizationFields
);

newSigningRole?.addEventListener(
    'change',
    applyNewRoleDefaults
);

document.addEventListener(
    'keydown',
    function (e) {
        if (
            e.key === 'Escape' &&
            newInvitationModal?.classList.contains('show')
        ) {
            closeNewModal();
        }
    }
);

toggleNewOrganizationFields();
applyNewRoleDefaults();