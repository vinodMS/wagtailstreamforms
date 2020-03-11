import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _

from wagtail.admin.edit_handlers import (
    FieldPanel,
    TabbedInterface,
    ObjectList,
    PageChooserPanel,
    MultiFieldPanel,
    StreamFieldPanel
)

from wagtailstreamforms import hooks
from wagtailstreamforms.conf import get_setting
from wagtailstreamforms.fields import HookSelectField
from wagtailstreamforms.forms import FormBuilder
from wagtailstreamforms.streamfield import FormFieldsStreamField
from wagtailstreamforms.utils.general import get_slug_from_string
from wagtailstreamforms.utils.loading import get_advanced_settings_model

from .submission import FormSubmission


class Form(models.Model):
    """ The form class. """

    title = models.CharField(
        _('Title'),
        max_length=255
    )
    slug = models.SlugField(
        _('Slug'),
        allow_unicode=True,
        max_length=255,
        unique=True,
        help_text=_('Used to identify the form in template tags')
    )
    template_name = models.CharField(
        _('Template'),
        max_length=255,
        choices=get_setting('FORM_TEMPLATES')
    )
    fields = FormFieldsStreamField(
        [],
        verbose_name=_('Fields')
    )
    submit_button_text = models.CharField(
        _('Submit button text'),
        max_length=100,
        default='Submit'
    )
    success_message = models.CharField(
        _('Success message'),
        blank=True,
        max_length=255,
        help_text=_('An optional success message to show when the form has been successfully submitted')
    )
    error_message = models.CharField(
        _('Error message'),
        blank=True,
        max_length=255,
        help_text=_('An optional error message to show when the form has validation errors')
    )
    post_redirect_page = models.ForeignKey(
        'wagtailcore.Page',
        verbose_name=_('Post redirect page'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text=_('The page to redirect to after a successful submission')
    )
    process_form_submission_hooks = HookSelectField(
        verbose_name=_('Submission hooks'),
        blank=True
    )

    settings_panels = [
        FieldPanel('title', classname='full'),
        FieldPanel('slug'),
        FieldPanel('template_name'),
        FieldPanel('submit_button_text'),
        MultiFieldPanel([
            FieldPanel('success_message'),
            FieldPanel('error_message'),
        ], _('Messages')),
        FieldPanel('process_form_submission_hooks', classname='choice_field'),
        PageChooserPanel('post_redirect_page')
    ]

    field_panels = [
        StreamFieldPanel('fields'),
    ]

    edit_handler = TabbedInterface([
        ObjectList(settings_panels, heading=_('General')),
        ObjectList(field_panels, heading=_('Fields')),
    ])

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title', ]
        verbose_name = _('Form')
        verbose_name_plural = _('Forms')

    def copy(self):
        """ Copy this form and its fields. """

        form_copy = Form(
            title=self.title,
            slug=uuid.uuid4(),
            template_name=self.template_name,
            fields=self.fields,
            submit_button_text=self.submit_button_text,
            success_message=self.success_message,
            error_message=self.error_message,
            post_redirect_page=self.post_redirect_page,
            process_form_submission_hooks=self.process_form_submission_hooks
        )
        form_copy.save()

        # additionally copy the advanced settings if they exist
        SettingsModel = get_advanced_settings_model()

        if SettingsModel:
            try:
                advanced = SettingsModel.objects.get(form=self)
                advanced.pk = None
                advanced.form = form_copy
                advanced.save()
            except SettingsModel.DoesNotExist:
                pass

        return form_copy

    copy.alters_data = True

    def get_data_fields(self):
        """ Returns a list of tuples with (field_name, field_label). """

        data_fields = [
            ('submit_time', _('Submission date')),
        ]
        data_fields += [
            (get_slug_from_string(field['value']['label']), field['value']['label'])
            for field in self.get_form_fields()
        ]

        return data_fields

	def get_data_fields_v2(self):
	    """ Returns a list of tuples with (field_name, field_label). """

	    data_fields = [
	        ('submit_time', _('Submission date')),
	    ]
	    data_fields += [
	        (get_slug_from_string(field['id']), field['value']['label'])
	        for field in self.get_form_fields()
	    ]

	    return data_fields


    def get_form(self, *args, **kwargs):
        """ Returns the form. """

        form_class = self.get_form_class()
        return form_class(*args, **kwargs)

    def get_form_class(self):
        """ Returns the form class. """

        return FormBuilder(self.get_form_fields()).get_form_class()

    def get_form_fields(self):
        """ Returns the form fields stream_data. """

        return self.fields.stream_data

    def get_submission_class(self):
        """ Returns submission class. """

        return FormSubmission

    def process_form_submission(self, form):
        """ Runs each hook if selected in the form. """

        for fn in hooks.get_hooks('process_form_submission'):
            if fn.__name__ in self.process_form_submission_hooks:
                fn(self, form)
