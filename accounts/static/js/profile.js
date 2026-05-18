function enableEdit() {
    // Enable all disabled inputs
    document.querySelectorAll('.profile-input[disabled]').forEach(input => {
        input.removeAttribute('disabled');
        input.classList.add('active');
    });

    // Show name edit fields
    document.getElementById('full-name-display').style.display = 'none';
    document.getElementById('full-name-edit').style.display = 'flex';
    
    // Add active class to name inputs
    document.querySelectorAll('#full-name-edit .profile-input').forEach(input => {
        input.classList.add('active');
    });

    // Show camera
    document.getElementById('avatar-label').style.display = 'flex';

    // Show save button
    document.getElementById('save-row').style.display = 'flex';

    // Hide edit button
    document.getElementById('edit-btn').style.display = 'none';
}
