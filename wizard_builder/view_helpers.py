import logging

from django.core.urlresolvers import reverse

logger = logging.getLogger(__name__)


class SerializedDataHelper(object):
    # TODO: move the zip functionality to PageForm or FormManager
    conditional_fields = [
        'extra_info',
        'extra_options',
    ]
    question_id_error_message = 'field_id={} not found in {}'
    choice_id_error_message = 'Choice(pk={}) not found in {}'
    choice_option_id_error_message = 'ChoiceOption(pk={}) not found in {}'

    @classmethod
    def get_zipped_data(cls, storage):
        return cls(storage).zipped_data

    def __init__(self, storage):
        self.storage = storage
        self.zipped_data = []
        self._format_data()

    def _format_data(self):
        for index, page_data in enumerate(self.storage.form_data['data']):
            self._cleaned_form_data(page_data, index)

    def _cleaned_form_data(self, page_data, index):
        self._parse_answer_fields(
            page_data,
            self._form_questions_serialized(index),
        )

    def _form_questions_serialized(self, index):
        return self.storage.view.forms[index].serialized

    def _parse_answer_fields(self, answers, questions):
        for answer_key, answer_value in answers.items():
            if answer_key not in self.conditional_fields:
                question = self._get_question(answer_key, questions)
                answer = self._question_answer(answers, question)
                self._parse_answers(questions, question, answers, answer)

    def _parse_answers(self, question_dict, question, answer_dict, answer):
        if question['type'] == 'Singlelinetext':
            self._append_text_answer(answer, question)
        else:
            answer_list = answer if isinstance(answer, list) else [answer]
            self._append_list_answers(answer_dict, answer_list, question)

    def _question_answer(self, answers, question):
        return answers[question['field_id']]

    def _append_text_answer(self, answer, question):
        if len(answer) > 0:
            self.zipped_data.append({
                question['question_text']: [answer],
            })

    def _append_list_answers(self, answer_dict, answer_list, question):
        choice_list = []
        for answer in answer_list:
            choice_list.append(self._get_choice_text(
                answer_dict, answer, question))
        self.zipped_data.append({
            question['question_text']: choice_list,
        })

    def _get_question(self, answer_key, questions):
        return self._get_from_serialized_id(
            stored_id=answer_key,
            current_objects=questions,
            id_field='field_id',
            message=self.question_id_error_message,
        )

    def _get_choice_text(self, answer_dict, answer, question):
        choice = self._get_from_serialized_id(
            stored_id=answer,
            current_objects=question['choices'],
            id_field='pk',
            message=self.choice_id_error_message,
        )
        choice_text = choice.get('text')
        if choice.get('extra_info_text') and answer_dict.get('extra_info'):
            choice_text += ': ' + answer_dict['extra_info']
        if choice.get('options') and answer_dict.get('extra_options'):
            choice_text += ': ' + self._get_choice_option_text(
                choice, answer_dict)
        return choice_text

    def _get_choice_option_text(self, choice, answer_dict):
        return self._get_from_serialized_id(
            stored_id=answer_dict['extra_options'],
            current_objects=choice['options'],
            id_field='pk',
            message=self.choice_option_id_error_message,
        ).get('text')

    def _get_from_serialized_id(
        self,
        stored_id,
        current_objects,
        id_field,
        message,
    ):
        try:
            related_object = None
            for _object in current_objects:
                if str(stored_id) == str(_object[id_field]):
                    related_object = _object
            if related_object is not None:
                return related_object
            else:
                raise ValueError(message.format(stored_id, current_objects))
        except Exception as e:
            # Catch exceptions raised from data being edited
            # after the user originally answered them
            logger.exception(e)
            return {}


class StepsHelper(object):
    done_name = 'done'
    review_name = 'Review'
    next_name = 'Next'
    back_name = 'Back'
    wizard_goto_name = 'wizard_goto_step'
    wizard_current_name = 'wizard_current_step'
    wizard_form_fields = [
        wizard_current_name,
        wizard_goto_name,
    ]

    def __init__(self, view):
        self.view = view

    @property
    def step_count(self):
        return len(self.view.forms)

    @property
    def current(self):
        step = getattr(self.view, 'curent_step', 0)
        if isinstance(step, str):
            return step
        elif step <= self.last:
            return step
        else:
            return self.last

    @property
    def last(self):
        return self.step_count - 1

    @property
    def next(self):
        return self.adjust_step(1)

    @property
    def next_is_done(self):
        if isinstance(self.current, int):
            return self.next == self.done_name
        else:
            return False

    @property
    def current_is_done(self):
        return self.current == self.done_name

    @property
    def current_url(self):
        return self.url(self.current)

    @property
    def last_url(self):
        return self.url(self.last)

    @property
    def done_url(self):
        return self.url(self.done_name)

    @property
    def _goto_step_back(self):
        return self._goto_step(self.back_name)

    @property
    def _goto_step_next(self):
        return self._goto_step(self.next_name)

    @property
    def _goto_step_review(self):
        return self._goto_step(self.review_name)

    def parse_step(self, step):
        if step == self.done_name:
            return step
        else:
            return int(step)

    def url(self, step):
        return reverse(
            self.view.request.resolver_match.view_name,
            kwargs={'step': step},
        )

    def overflowed(self, step):
        return int(step) > int(self.last)

    def finished(self, step):
        return self._goto_step_review or step == self.done_name

    def set_from_post(self):
        if self._goto_step_back:
            self.view.curent_step = self.adjust_step(-1)
        if self._goto_step_next:
            self.view.curent_step = self.adjust_step(1)

    def adjust_step(self, adjustment):
        step = self.view.curent_step + adjustment
        if step >= self.step_count:
            return self.done_name
        else:
            return step

    def _goto_step(self, step_type):
        post = self.view.request.POST
        return post.get(self.wizard_goto_name, None) == step_type


class StorageHelper(object):
    data_manager = SerializedDataHelper
    form_pk_field = 'form_pk_field'

    def __init__(self, view):
        self.view = view

    @property
    def form_data(self):
        return {'data': [
            self.current_data_from_pk(form.pk)
            for form in self.view.forms
        ]}

    @property
    def cleaned_form_data(self):
        return self.data_manager.get_zipped_data(self)

    @property
    def post_form_pk(self):
        pk = self.view.request.POST[self.form_pk_field]
        return self.form_pk(pk)

    @property
    def current_and_post_data(self):
        current_data = self.current_data_from_key(self.post_form_pk)
        post_data = self._data_without_metadata(self.view.request.POST)
        current_data.update(post_data)
        return current_data

    @property
    def metadata_fields(self):
        return [
            'csrfmiddlewaretoken',
            self.form_pk_field,
        ] + self.view.steps.wizard_form_fields

    def form_pk(self, pk):
        return '{}_{}'.format(self.form_pk_field, pk)

    def update(self):
        data = self.current_data_from_storage()
        data[self.post_form_pk] = self.current_and_post_data
        self.add_data_to_storage(data)

    def current_data_from_pk(self, pk):
        key = self.form_pk(pk)
        return self.current_data_from_key(key)

    def current_data_from_key(self, form_key):
        data = self.current_data_from_storage()
        return data.get(form_key, {})

    def current_data_from_storage(self):
        return self.view.request.session.get('data', {})

    def add_data_to_storage(self, data):
        self.view.request.session['data'] = data

    def _data_without_metadata(self, data):
        return {
            key: value
            for key, value in dict(data).items()
            if key not in self.metadata_fields
        }
