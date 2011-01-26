from django import forms
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.forms.formsets import BaseFormSet

from ajax_validation.utils import LazyEncoder

def validate(request, *args, **kwargs):
    if 'save_session' in kwargs:
        save_session = kwargs['save_session']
    else:
        save_session = False
    
    if 'return_form_data' in kwargs and kwargs['return_form_data'] == True:
        return_form_data = True
    else:
        return_form_data = False
    
    form_class = kwargs.pop('form_class')
    defaults = {
        'data': request.POST
    }
    extra_args_func = kwargs.pop('callback', lambda request, *args, **kwargs: {})
    kwargs = extra_args_func(request, *args, **kwargs)
    defaults.update(kwargs)
    form = form_class(**defaults)
    if form.is_valid():
        # Conditionally save the post data for later use
        if save_session:
            # Save in simple dict if no session key given
            if type(save_session) == type(bool()):
                request.session[form.__class__.__name__] = form.cleaned_data if return_form_data else request.POST
            # Save in specified session key
            else:
                if not save_session in request.session:
                    request.session[save_session] = dict()
                request.session[save_session][form.__class__.__name__] = form.cleaned_data if return_form_data else request.POST
            # Make sure the updated session gets saved
            request.session.modified = True
        
        data = {
            'valid': True,
        }
        
        if return_form_data:
            data['form'] = form.cleaned_data
    else:
        # if we're dealing with a FormSet then walk over .forms to populate errors and formfields
        if isinstance(form, BaseFormSet):
            errors = {}
            formfields = {}
            for f in form.forms:
                for field in f.fields.keys():
                    formfields[f.add_prefix(field)] = f[field]
                for field, error in f.errors.iteritems():
                    errors[f.add_prefix(field)] = error
            if form.non_form_errors():
                errors['__all__'] = form.non_form_errors()
        else:
            errors = form.errors
            formfields = dict([(fieldname, form[fieldname]) for fieldname in form.fields.keys()])

        # if fields have been specified then restrict the error list
        if request.POST.getlist('fields'):
            fields = request.POST.getlist('fields') + ['__all__']
            errors = dict([(key, val) for key, val in errors.iteritems() if key in fields])

        final_errors = {}
        for key, val in errors.iteritems():
            if '__all__' in key:
                final_errors[key] = val
            elif not isinstance(formfields[key].field, forms.FileField):
                html_id = formfields[key].field.widget.attrs.get('id') or formfields[key].auto_id
                html_id = formfields[key].field.widget.id_for_label(html_id)
                final_errors[html_id] = val
        data = {
            'valid': False or not final_errors,
            'errors': final_errors,
        }
    json_serializer = LazyEncoder()
    return HttpResponse(json_serializer.encode(data), mimetype='application/json')
validate = require_POST(validate)
