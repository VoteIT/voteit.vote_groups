var Roles = Roles || {};

Roles.getForm = function(event) {
    return $(event.currentTarget).closest('form');
}

Roles.start = function(event) {
    event.preventDefault();
    $form = Roles.getForm(event);
    $form.addClass('editing');
}

Roles.save = function(event) {
    event.preventDefault();
    $form = Roles.getForm(event);
    $.post($form.prop('action'), $form.serializeArray())
    .done(function(result) {
        if (result.status !== 'success') {
            arche.create_flash_message(result.error_message, {type: 'danger'});
        } else if (result.changed_roles == 0) {
            $form.removeClass('editing');
        } else {
            window.location.reload();
        }
    })
    .fail(function(response) {
        arche.flash_error(response);
    })
}

$(function() {
    $('[data-edit-roles]').click(Roles.start);
    $('[data-save-roles]').click(Roles.save);
})
