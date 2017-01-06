"""
A named entity recognizer in the file system operation domain.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import re

from . import constants

_SIZE = "_SIZE"
_TIMESPAN = "_TIMESPAN"
_DATETIME = "_DATETIME"
_PATH = "_PATH"
_FILE = "_FILE"
_DIRECTORY = "_DIRECTORY"
_PERMISSION = "_PERMISSION"
_OTHER_PATTERN = "_OTHER_PATTERN"

def add_space(s):
    return ' {} '.format(s)

def quotation_safe(r):
    return r'\s"?' + r + r'"?(\s|$)'

_DIGIT_RE = re.compile(quotation_safe(r"\d+(.\d+)?"))

_WORD_SPLIT_RESPECT_QUOTES = re.compile('(?:[^\s,"]|"(?:\\.|[^"])*")+')

def annotate(tokens):
    """
    Identify named entities in a (tokenized) sentence and replace them with the
    corresponding categories.

    The NER so far recognizes the following named entity categories:
    - Pattern-based:
        - File
        - Directory
        - Path
        - Permission
        - Username
        - Groupname
        - DateTime
        - Other Patterns
    - Quantity-based:
        - Number
        - Size
        - Timespan

    :return: 1. a list of tokens where the named entities are replaced with
        category names
             2. a dictionary that stores a list of named entities matched for
        each category
    """

    sentence = ' '.join(tokens)
    entities = collections.defaultdict(list)

    _SIZE_UNIT = r'(b|k|m|g|t|kb|mb|gb|tb|byt|byte|kilobyt|kilobyte|kilo byte|' \
             r'megabyt|megabyte|mega byte|gigabyt|gigabyte|terabyt|terabyte)'

    _DURATION_UNIT = r'(s|m|h|d|w|y|sec|second|min|minut|minute|hour|day|week|' \
             r'mon|month|year)'

    # Credit: time expressions adapted from
    # https://github.com/nltk/nltk_contrib/blob/master/nltk_contrib/timex.py
    month = r'(january|jan|jan.|february|feb|feb.|march|mar|mar.|april|apr|apr.|' \
            r'may|june|jun|jun.|july|jul|jul.|august|aug|aug.|september|sep|sep.|' \
            r'october|oct|oct.|november|nov|nov.|december|dec|dec.)'
    rel_day = r'(today|yesterday|tomorrow|the day before yesterday|' \
              r'the day after tomorrow)'
    standard_time = r'\d+:\d+:\d+\.?\d*'
    standard_datetime = r'\d{1,4}[/-]\d{1,4}[/-]\d{1,4}' \
                        r'[,|\s]' + '(' + standard_time + ')?'
    textual_datetime = month + r'(\s\d{0,2})?([,|\s]\d{2,4})?' \
                        r'[,|\s]' + r'(' + standard_time + r')?'

    numerical_permission = r'[+|-]?[0-7]{3,4}'
    pattern_permission = r'([u|g|o]+[+|-|=][r|w|x|s|u|t]+)+'
    permission_bit = r'(suid|sgid|sticky|sticki)(\sbit)?'
    permission_bit_set = r'(set)*(uid|gid|sticky|sticki)(=\d+)*'
    # -- Size
    _SIZE_RE = re.compile(quotation_safe(r'(\d+|a)\s*' + _SIZE_UNIT))
    sentence = annotate_ner(_SIZE_RE, _SIZE, sentence, entities)

    # -- Timespan
    _DURATION_RE = re.compile(quotation_safe(
        r'(\d+|a|this|next(\s\d+)?|last(\s\d+)?|previous(\s\d+)?)\s*' + _DURATION_UNIT))
    sentence = annotate_ner(_DURATION_RE, _TIMESPAN, sentence, entities)

    # -- DateTime
    _DATETIME_RE = re.compile(quotation_safe('(' + rel_day + '|' +
                    standard_time + '|' + standard_datetime + '|' +
                    textual_datetime + ')' + r'"?(\s|$)'))
    sentence = annotate_ner(_DATETIME_RE, _DATETIME, sentence, entities)

    # -- Permission
    _PERMISSION_RE = re.compile(quotation_safe('(' + numerical_permission + '|' +
                    pattern_permission + '|' + permission_bit + '|' +
                    permission_bit_set + ')'))
    sentence = annotate_ner(_PERMISSION_RE, _PERMISSION, sentence, entities)

    # -- Number
    sentence = annotate_ner(_DIGIT_RE, constants._NUMBER, sentence, entities)

    # -- Path
    _PATH_RE = re.compile(quotation_safe(r'([^ ]*\/)+[^ ]*'))
    sentence = annotate_ner(_PATH_RE, _PATH, sentence, entities)

    # -- File/Directory
    file_extensions = r'(aiff|cda|mid|mp3|mp4|mpa|ogg|wav|wma|wpl|7z|arj|deb|' \
                      r'pkg|rar|rpm|tar|gz|zip|bin|dmg|iso|vcd|vcr|dvd|csv|' \
                      r'dat|db|log|mdb|sav|sql|tar|xml|apk|bat|bin|cgi|pl|com|' \
                      r'html|css|js|exe|gadget|jar|py|wsf|fnt|fon|otf|ttf|ai|' \
                      r'bmp|gif|ico|jpg|jpeg|png|psd|svg|tif|java|php|txt|c|' \
                      r'cpp|cc|o|htm|asp|cer|jsp|json|rss|xhtml|odp|ppt|pptx|' \
                      r'class|h|sh|swift|vb|ods|xlr|xlsx|xls|ini|msi|sys|tmp|' \
                      r'drv|dmp|dll|bak|3gp|flv|h264|avi|mkv|mov|m4v|rm|mpg|' \
                      r'mpeg|swf|wmv|doc|docx|tex|pdf|rtf|wps|wpd|xz|cvs)'
    _FILE_RE = re.compile(quotation_safe(r'([^ ]*\.[^ ]*|' + file_extensions + ')'))
    sentence = annotate_ner(_FILE_RE, _FILE, sentence, entities)

    # -- Other patterns
    _REGEX_RE = re.compile(r'\s(".+"|.*[\*|\\|\~|\@|\%|\#|\?|\+|\$|\{|\}]+.*)(\s|$)')
    sentence = annotate_ner(_REGEX_RE, constants._REGEX, sentence, entities)

    normalized_words = []
    words = re.findall(_WORD_SPLIT_RESPECT_QUOTES, sentence)
    for w in words:
        if not w.startswith('_') and not is_english_word(w):
            normalized_words.append(constants._REGEX)
        else:
            normalized_words.append(w)

    return normalized_words, entities

def annotate_ner(pattern, category, sentence, entities):
    for m in re.finditer(pattern, sentence):
        entities[category].append(sentence[m.start(0):m.end(0)].strip())
    sentence = re.sub(pattern, add_space(category), sentence).strip()
    return sentence

def normalize_number_in_token(token):
    return re.sub(_DIGIT_RE, constants._NUMBER, token)

def is_english_word(word):
    """Check if a token is normal English word."""
    if any(x.isalpha() for x in word):
        if word[-1].isdigit():
            return False
    if word.isalpha() and any(x.isupper() for x in word):
        return False
    return bool(re.match('[0-9A-Za-z\-\'\(\)]+$', word, re.IGNORECASE))