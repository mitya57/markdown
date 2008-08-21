#!/usr/bin/env python
"""
Python-Markdown
===============

Converts Markdown to HTML.  Basic usage as a module:

    import markdown
    md = Markdown()
    html = md.convert(your_text_string)

See <http://www.freewisdom.org/projects/python-markdown/> for more
information and instructions on how to extend the functionality of the
script.  (You might want to read that before you try modifying this
file.)

Started by [Manfred Stienstra](http://www.dwerg.net/).  Continued and
maintained  by [Yuri Takhteyev](http://www.freewisdom.org), [Waylan
Limberg](http://achinghead.com/) and [Artem Yunusov](http://blog.splyer.com).

Contact: 

* <yuri@freewisdom.org>
* <waylan@gmail.com>

License: [GPL 2](http://www.gnu.org/copyleft/gpl.html) or BSD

"""

version = "2.0-alpha"
version_info = (2,0,0, "beta")

import re, sys, codecs, htmlentitydefs
from urlparse import urlparse, urlunparse

from logging import getLogger, StreamHandler, Formatter, \
                    DEBUG, INFO, WARN, ERROR, CRITICAL

MESSAGE_THRESHOLD = CRITICAL

# Configure debug message logger (the hard way - to support python 2.3)
logger = getLogger('MARKDOWN')
logger.setLevel(DEBUG) # This is restricted by handlers later
console_hndlr = StreamHandler()
formatter = Formatter('%(name)s-%(levelname)s: "%(message)s"')
console_hndlr.setFormatter(formatter)
console_hndlr.setLevel(MESSAGE_THRESHOLD)
logger.addHandler(console_hndlr)


def message(level, text):
    ''' A wrapper method for logging debug messages. '''
    logger.log(level, text)
    
def isstr(s):
    """ Check if it's string """
    return isinstance(s, unicode) or isinstance(s, str)
 
def importETree(): 
    """ Import best variant of ElementTree and return module object """
    cetree = None  
    try:
        # Python 2.5+
        import xml.etree.cElementTree as cetree
    except ImportError:
        try:
            # Python 2.5+
            import xml.etree.ElementTree as etree
        except ImportError:
            try:
                # normal cElementTree install
                import cElementTree as cetree
            except ImportError:
                try:
                    # normal ElementTree install
                    import elementtree.ElementTree as etree
                except ImportError:
                    message(CRITICAL, 
                           "Failed to import ElementTree from any known place")
                    sys.exit(1)
    if cetree:
        if cetree.VERSION < "1.0":
            message(CRITICAL, 
                           "cElementTree version is too old, 1.0 and upper required")
            sys.exit(1)
            
        etree = cetree
    else:
        if etree.VERSION < "1.1":
            message(CRITICAL, 
                           "ElementTree version is too old, 1.1 and upper required")
            sys.exit(1)
            
    return etree

"""ElementTree module
in extensions use: `from markdown import etree`
to access to the ElemetTree module, do not import it by yourself"""
etree = importETree() 

def indentETree(elem, level=0):
    """ Indent ElementTree before serialization """
     
    if level > 1:
        i = "\n" + (level-1) * "  "
    else:
        i = "\n"

    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indentETree(e, level+1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
        
class AtomicString(unicode):
    "A string which should not be further processed."
    pass

# --------------- CONSTANTS YOU MIGHT WANT TO MODIFY -----------------

TAB_LENGTH = 4            # expand tabs to this many spaces
ENABLE_ATTRIBUTES = True  # @id = xyz -> <... id="xyz">
SMART_EMPHASIS = True        # this_or_that does not become this<i>or</i>that
HTML_REMOVED_TEXT = "[HTML_REMOVED]" # text used instead of HTML in safe mode

RTL_BIDI_RANGES = ( (u'\u0590', u'\u07FF'),
                    # from Hebrew to Nko (includes Arabic, Syriac and Thaana)
                    (u'\u2D30', u'\u2D7F'),
                    # Tifinagh
                    )

# Unicode Reference Table:
# 0590-05FF - Hebrew
# 0600-06FF - Arabic
# 0700-074F - Syriac
# 0750-077F - Arabic Supplement
# 0780-07BF - Thaana
# 07C0-07FF - Nko

BOMS = { 'utf-8': (codecs.BOM_UTF8, ),
         'utf-16': (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE),
         #'utf-32': (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)
         }

def removeBOM(text, encoding):
    """
    Used by `markdownFromFile` to remove a "byte order mark" from the begining
    of an utf-8, utf-16 or utf-32 encoded file.
    """
    
    convert = isinstance(text, unicode)
    for bom in BOMS[encoding]:
        bom = convert and bom.decode(encoding) or bom
        if text.startswith(bom):
            return text.lstrip(bom)
    return text


# The following constant specifies the name used in the usage
# statement displayed for python versions lower than 2.3.  (With
# python2.3 and higher the usage statement is generated by optparse
# and uses the actual name of the executable called.)

EXECUTABLE_NAME_FOR_USAGE = "python markdown.py"
                    

# --------------- CONSTANTS YOU _SHOULD NOT_ HAVE TO CHANGE ----------


# placeholders
STX = u'\u0002'  # Use STX ("Start of text") for start-of-placeholder
ETX = u'\u0003'  # Use ETX ("End of text") for end-of-placeholder
HTML_PLACEHOLDER_PREFIX = STX+"html:"
HTML_PLACEHOLDER = HTML_PLACEHOLDER_PREFIX + "%d"+ETX
INLINE_PLACEHOLDER_PREFIX = STX+"inline:"
INLINE_PLACEHOLDER_SUFFIX = ETX

AMP_SUBSTITUTE = STX+"amp"+ETX 


BLOCK_LEVEL_ELEMENTS = ['p', 'div', 'blockquote', 'pre', 'table',
                        'dl', 'ol', 'ul', 'script', 'noscript',
                        'form', 'fieldset', 'iframe', 'math', 'ins',
                        'del', 'hr', 'hr/', 'style']

def isBlockLevel (tag):
    """
    Used by HTMLBlockPreprocessor to check if a given tag is a block level 
    element.
    """
    return ( (tag in BLOCK_LEVEL_ELEMENTS) or
             (tag[0] == 'h' and tag[1] in "0123456789") )


def codepoint2name(code):
    """ 
    Return entity definition by code, or code 
    if there is no such entity definition
    """
    entity = htmlentitydefs.codepoint2name.get(code)
    if entity:
        return "%s%s;" % (AMP_SUBSTITUTE, entity)
    else:
        return "%s#%d;" % (AMP_SUBSTITUTE, code)
    
def handleAttributes(text, parent):
    """ Handale attributes, e.g {@id=123} """
    def attributeCallback(match):
        parent.set(match.group(1), match.group(2))

    return RE.regExp['attr'].sub(attributeCallback, text)
    

"""
======================================================================
========================== PRE-PROCESSORS ============================
======================================================================

Preprocessors munge source text before we start doing anything too
complicated.

There are two types of preprocessors: TextPreprocessor and Preprocessor.

"""


class TextPreprocessor:
    """
    TextPreprocessors are run before the text is broken into lines.
    
    Each TextPreprocessor implements a "run" method that takes a pointer to a
    text string of the document, modifies it as necessary and returns
    either the same pointer or a pointer to a new string.  
    
    TextPreprocessors must extend markdown.TextPreprocessor.

    """

    def run(self, text):
        """ 
        Each subclass of TextPreprocessor should override the `run` method, 
        which takes the document text as a single string and returns the 
        (possibly modified) document as a single string.
        
        """
        pass


class Preprocessor:
    """
    Preprocessors are run after the text is broken into lines.

    Each preprocessor implements a "run" method that takes a pointer to a
    list of lines of the document, modifies it as necessary and returns
    either the same pointer or a pointer to a new list.  
    
    Preprocessors must extend markdown.Preprocessor.
    
    """

    def run(self, lines):
        """
        Each subclass of Preprocessor should override the `run` method, which
        takes the document as a list of strings split by newlines and returns
        the (possibly modified) list of lines.

        """
        pass
 

class HtmlBlockPreprocessor(TextPreprocessor):
    """
    Remove html blocks from the source text and store them for later retrieval.
    """
    
    def _get_left_tag(self, block):
        return block[1:].replace(">", " ", 1).split()[0].lower()


    def _get_right_tag(self, left_tag, block):
        return block.rstrip()[-len(left_tag)-2:-1].lower()

    def _equal_tags(self, left_tag, right_tag):
        
        if left_tag == 'div' or left_tag[0] in ['?', '@', '%']: # handle PHP, etc.
            return True
        if ("/" + left_tag) == right_tag:
            return True
        if (right_tag == "--" and left_tag == "--"):
            return True
        elif left_tag == right_tag[1:] \
            and right_tag[0] != "<":
            return True
        else:
            return False

    def _is_oneliner(self, tag):
        return (tag in ['hr', 'hr/'])

    
    def run(self, text):
        """ Find and remove raw html from text. """

        new_blocks = []
        text = text.split("\n\n")
        
        items = []
        left_tag = ''
        right_tag = ''
        in_tag = False # flag
        
        for block in text:
            if block.startswith("\n"):
                block = block[1:]

            if not in_tag:

                if block.startswith("<"):
                    
                    left_tag = self._get_left_tag(block)
                    right_tag = self._get_right_tag(left_tag, block)

                    if not (isBlockLevel(left_tag) \
                        or block[1] in ["!", "?", "@", "%"]):
                        new_blocks.append(block)
                        continue

                    if self._is_oneliner(left_tag):
                        new_blocks.append(block.strip())
                        continue
                        
                    if block[1] == "!":
                        # is a comment block
                        left_tag = "--"
                        right_tag = self._get_right_tag(left_tag, block)
                        # keep checking conditions below and maybe just append
                        
                    if block.rstrip().endswith(">") \
                        and self._equal_tags(left_tag, right_tag):
                        new_blocks.append(
                            self.stash.store(block.strip()))
                        continue
                    else: #if not block[1] == "!":
                        # if is block level tag and is not complete
                        items.append(block.strip())
                        in_tag = True
                        continue

                new_blocks.append(block)

            else:
                items.append(block.strip())
                
                right_tag = self._get_right_tag(left_tag, block)
                
                if self._equal_tags(left_tag, right_tag):
                    # if find closing tag
                    in_tag = False
                    new_blocks.append(
                        self.stash.store('\n\n'.join(items)))
                    items = []

        if items:
            new_blocks.append(self.stash.store('\n\n'.join(items)))
            new_blocks.append('\n')
            
        return "\n\n".join(new_blocks)

HTML_BLOCK_PREPROCESSOR = HtmlBlockPreprocessor()


class HeaderPreprocessor(Preprocessor):

    """
    Replace underlined headers with hashed headers to avoid
    the need for lookahead later.
    """

    def run (self, lines):
        """ Find and replace underlined headers. """

        i = -1
        while i+1 < len(lines):
            i = i+1
            if not lines[i].strip():
                continue

            if lines[i].startswith("#"):
                lines.insert(i+1, "\n")

            if (i+1 <= len(lines)
                  and lines[i+1]
                  and lines[i+1][0] in ['-', '=']):

                underline = lines[i+1].strip()

                if underline == "="*len(underline):
                    lines[i] = "# " + lines[i].strip()
                    lines[i+1] = ""
                elif underline == "-"*len(underline):
                    lines[i] = "## " + lines[i].strip()
                    lines[i+1] = ""

        return lines

HEADER_PREPROCESSOR = HeaderPreprocessor()


class LinePreprocessor(Preprocessor):
    """ 
    Convert HR lines to "___" format 
    """

    blockquote_re = re.compile(r'^(> )+')

    def run (self, lines):
        """ Find and replace HR lines. """

        for i in range(len(lines)):
            prefix = ''
            m = self.blockquote_re.search(lines[i])
            if m: 
                prefix = m.group(0)
            if self._isLine(lines[i][len(prefix):]):
                lines[i] = prefix + "___"
        return lines

    def _isLine(self, block):
        """Determine if a block should be replaced with an <HR>"""

        if block.startswith("    "): 
            return False  # a code block
        text = "".join([x for x in block if not x.isspace()])
        if len(text) <= 2:
            return False
        for pattern in ['isline1', 'isline2', 'isline3']:
            m = RE.regExp[pattern].match(text)
            if (m and m.group(1)):
                return True
        else:
            return False

LINE_PREPROCESSOR = LinePreprocessor()


class ReferencePreprocessor(Preprocessor):
    """
    Remove reference definitions from the text and store them for later use.
    
    """

    def run (self, lines):
        """ Remove and store reference defs. """
        new_text = [];
        for line in lines:
            m = RE.regExp['reference-def'].match(line)
            if m:
                id = m.group(2).strip().lower()
                t = m.group(4).strip()  # potential title
                if not t:
                    self.references[id] = (m.group(3), t)
                elif (len(t) >= 2
                      and (t[0] == t[-1] == "\""
                           or t[0] == t[-1] == "\'"
                           or (t[0] == "(" and t[-1] == ")") ) ):
                    self.references[id] = (m.group(3), t[1:-1])
                else:
                    new_text.append(line)
            else:
                new_text.append(line)

        return new_text #+ "\n"

REFERENCE_PREPROCESSOR = ReferencePreprocessor()


"""
======================================================================
========================== INLINE PATTERNS ===========================
======================================================================

Inline patterns such as *emphasis* are handled by means of auxiliary
objects, one per pattern.  Pattern objects must be instances of classes
that extend markdown.Pattern.  Each pattern object uses a single regular
expression and needs support the following methods:

  pattern.getCompiledRegExp() - returns a regular expression

  pattern.handleMatch(m) - takes a match object and returns
                                a ElementTree element or just plain text

All of python markdown's built-in patterns subclass from Pattern,
but you can add additional patterns that don't.

Also note that all the regular expressions used by inline must
capture the whole block.  For this reason, they all start with
'^(.*)' and end with '(.*)!'.  In case with built-in expression
Pattern takes care of adding the "^(.*)" and "(.*)!".

Finally, the order in which regular expressions are applied is very
important - e.g. if we first replace http://.../ links with <a> tags
and _then_ try to replace inline html, we would end up with a mess.
So, we apply the expressions in the following order:

       * escape and backticks have to go before everything else, so
         that we can preempt any markdown patterns by escaping them.

       * then we handle auto-links (must be done before inline html)

       * then we handle inline HTML.  At this point we will simply
         replace all inline HTML strings with a placeholder and add
         the actual HTML to a hash.

       * then inline images (must be done before links)

       * then bracketed links, first regular then reference-style

       * finally we apply strong and emphasis
"""

NOBRACKET = r'[^\]\[]*'
BRK = ( r'\[('
        + (NOBRACKET + r'(\[')*6
        + (NOBRACKET+ r'\])*')*6
        + NOBRACKET + r')\]' )
NOIMG = r'(?<!\!)'

BACKTICK_RE = r'(?<!\\)(`+)(.+?)(?<!`)\2(?!`)' # `e=f()` or ``e=f("`")``
ESCAPE_RE = r'\\(.)'                             # \<
EMPHASIS_RE = r'(\*)([^\*]*)\2'                    # *emphasis*
STRONG_RE = r'(\*{2}|_{2})(.*?)\2'                      # **strong**
STRONG_EM_RE = r'(\*{3}|_{3})(.*?)\2'            # ***strong***

if SMART_EMPHASIS:
    EMPHASIS_2_RE = r'(?<!\S)(_)(\S.*?)\2'        # _emphasis_
else:
    EMPHASIS_2_RE = r'(_)(.*?)\2'                 # _emphasis_

LINK_RE = NOIMG + BRK + \
r'''\(\s*(<.*?>|((?:(?:\(.*?\))|[^\(\)]))*?)\s*((['"])(.*)\12)?\)''' # [text](url) or [text](<url>)

IMAGE_LINK_RE = r'\!' + BRK + r'\s*\((<.*?>|([^\)]*))\)' # ![alttxt](http://x.com/) or ![alttxt](<http://x.com/>)
REFERENCE_RE = NOIMG + BRK+ r'\s*\[([^\]]*)\]'           # [Google][3]
IMAGE_REFERENCE_RE = r'\!' + BRK + '\s*\[([^\]]*)\]' # ![alt text][2]
NOT_STRONG_RE = r'( \* )'                        # stand-alone * or _
AUTOLINK_RE = r'<((?:f|ht)tps?://[^>]*)>'        # <http://www.123.com>
AUTOMAIL_RE = r'<([^> \!]*@[^> ]*)>'               # <me@example.com>

HTML_RE = r'(\<([a-zA-Z/][^\>]*?|\!--.*?--)\>)'               # <...>
ENTITY_RE = r'(&[\#a-zA-Z0-9]*;)'               # &amp;
LINE_BREAK_RE = r'  \n'                     # two spaces at end of line
LINE_BREAK_2_RE = r'  $'                    # two spaces at end of text

class Pattern:
    """Base class that inline patterns subclass. """

    def __init__ (self, pattern):
        """
        Create an instant of an inline pattern.

        Keyword arguments:

        * pattern: A regular expression that matches a pattern

        """
        self.pattern = pattern
        self.compiled_re = re.compile("^(.*?)%s(.*?)$" % pattern, re.DOTALL)

        # Api for Markdown to pass safe_mode into instance
        self.safe_mode = False

    def getCompiledRegExp (self):
        """ Return a compiled regular expression. """
        return self.compiled_re

    def handleMatch(self, m):
        """
        Return a ElementTree element from the given match. Subclasses should 
        override this method.

        Keyword arguments:

        * m: A re match object containing a match of the pattern.

        """
        pass
    
    def type(self):
        """ Return class name, to define pattern type """
        return self.__class__.__name__

BasePattern = Pattern # for backward compatibility

class SimpleTextPattern (Pattern):
    """ Return a simple text of group(2) of a Pattern. """
    def handleMatch(self, m):
        text = m.group(2)
        if text == INLINE_PLACEHOLDER_PREFIX:
            return None
        return text

class SimpleTagPattern (Pattern):
    """ 
    Return element of type `tag` with a text attribute of group(3) 
    of a Pattern. 
    
    """
    def __init__ (self, pattern, tag):
        Pattern.__init__(self, pattern)
        self.tag = tag

    def handleMatch(self, m):
        el = etree.Element(self.tag)
        el.text = m.group(3)
        return el

class SubstituteTagPattern (SimpleTagPattern):
    """ Return a eLement of type `tag` with no children. """
    def handleMatch (self, m):
        return etree.Element(self.tag)

class BacktickPattern (Pattern):
    """ Return a `<code>` element containing the matching text. """
    def __init__ (self, pattern):
        Pattern.__init__(self, pattern)
        self.tag = "code"

    def handleMatch(self, m):
        el = etree.Element(self.tag)
        el.text = m.group(3).strip()
        return el


class DoubleTagPattern (SimpleTagPattern): 
    """ 
    Return a ElementTree element nested in tag2 nested in tag1. 
    Useful for strong emphasis etc.

    """
    def handleMatch(self, m):
        tag1, tag2 = self.tag.split(",")
        el1 = etree.Element(tag1)
        el2 = etree.SubElement(el1, tag2)
        el2.text = m.group(3)
        return el1


class HtmlPattern (Pattern):
    """ Store raw inline html and return a placeholder. """
    def handleMatch (self, m):
        rawhtml = m.group(2)
        inline = True
        place_holder = self.stash.store(rawhtml)
        return place_holder



class LinkPattern (Pattern):
    """ Return a link element from the given match. """
    def handleMatch(self, m):

        el = etree.Element("a")
        el.text = m.group(2)
        title = m.group(11)
        href = m.group(9)

        if href:
            if href[0] == "<":
                href = href[1:-1]
            el.set("href", self.sanatize_url(href.strip()))
        else:
            el.set("href", "")
            
        if title:
            title = dequote(title) #.replace('"', "&quot;")
            el.set("title", title)
        return el

    def sanatize_url(self, url):
        """ 
        Sanitize a url against xss attacks in "safe_mode".

        Rather than specifically blacklisting `javascript:alert("XSS")` and all
        its aliases (see <http://ha.ckers.org/xss.html>), we whitelist known
        safe url formats. Most urls contain a network location, however some 
        are known not to (i.e.: mailto links). Script urls do not contain a 
        location. Additionally, for `javascript:...`, the scheme would be 
        "javascript" but some aliases will appear to `urlparse()` to have no 
        scheme. On top of that relative links (i.e.: "foo/bar.html") have no 
        scheme. Therefore we must check "path", "parameters", "query" and 
        "fragment" for any literal colons. We don't check "scheme" for colons 
        because it *should* never have any and "netloc" must allow the form:
        `username:password@host:port`.
        
        """
        locless_schemes = ['', 'mailto', 'news']
        scheme, netloc, path, params, query, fragment = url = urlparse(url)
        safe_url = False
        if netloc != '' or scheme in locless_schemes:
            safe_url = True

        for part in url[2:]:
            if ":" in part:
                safe_url = False

        if self.safe_mode and not safe_url:
            return ''
        else:
            return urlunparse(url)

class ImagePattern(LinkPattern):
    """ Return a img element from the given match. """
        
    def handleMatch(self, m):
        el = etree.Element("img")
        src_parts = m.group(9).split()
        if src_parts:
            src = src_parts[0]
            if src[0] == "<" and src[-1] == ">":
                src = src[1:-1]
            el.set('src', self.sanatize_url(src))
        else:
            el.set('src', "")
        if len(src_parts) > 1:
            el.set('title', dequote(" ".join(src_parts[1:])))
  
        if ENABLE_ATTRIBUTES:
            truealt = handleAttributes(m.group(2), el)
        else:
            truealt = m.group(2)
            
        el.set('alt', truealt)
        return el

class ReferencePattern(LinkPattern):
    """ Match to a stored reference and return link element. """
    def handleMatch(self, m):

        if m.group(9):
            id = m.group(9).lower()
        else:
            # if we got something like "[Google][]"
            # we'll use "google" as the id
            id = m.group(2).lower()

        if not self.references.has_key(id): # ignore undefined refs
            return None
        href, title = self.references[id]

        text = m.group(2)
        return self.makeTag(href, title, text)

    def makeTag(self, href, title, text):
        el = etree.Element('a')
        
        el.set('href', self.sanatize_url(href))
        if title:
            el.set('title', title)

        el.text = text
        return el


class ImageReferencePattern (ReferencePattern):
    """ Match to a stored reference and return img element. """
    def makeTag(self, href, title, text):
        el = etree.Element("img")
        el.set("src", self.sanatize_url(href))
        if title:
            el.set("title", title)
        el.set("alt", text)
        return el


class AutolinkPattern (Pattern):
    """ Return a link Element given an autolink (`<http://example/com>`). """
    def handleMatch(self, m):
        el = etree.Element("a")
        el.set('href', m.group(2))
        el.text = m.group(2)
        return el

class AutomailPattern (Pattern):
    """ 
    Return a mailto link Element given an automail link (`<foo@example.com>`). 
    
    """
    def handleMatch(self, m):
        el = etree.Element('a')
        email = m.group(2)
        if email.startswith("mailto:"):
            email = email[len("mailto:"):]
        el.text = ""
        for letter in email:
            el.text += codepoint2name(ord(letter))

        mailto = "mailto:" + email
        mailto = "".join([AMP_SUBSTITUTE + '#%d;' % 
                          ord(letter) for letter in mailto])
        el.set('href', mailto)
        return el

ESCAPE_PATTERN          = SimpleTextPattern(ESCAPE_RE)
NOT_STRONG_PATTERN      = SimpleTextPattern(NOT_STRONG_RE)

BACKTICK_PATTERN        = BacktickPattern(BACKTICK_RE)
STRONG_PATTERN          = SimpleTagPattern(STRONG_RE, 'strong')
EMPHASIS_PATTERN        = SimpleTagPattern(EMPHASIS_RE, 'em')
EMPHASIS_PATTERN_2      = SimpleTagPattern(EMPHASIS_2_RE, 'em')

STRONG_EM_PATTERN       = DoubleTagPattern(STRONG_EM_RE, 'strong,em')

LINE_BREAK_PATTERN      = SubstituteTagPattern(LINE_BREAK_RE, 'br ')
LINE_BREAK_PATTERN_2    = SubstituteTagPattern(LINE_BREAK_2_RE, 'br ')

LINK_PATTERN            = LinkPattern(LINK_RE)
IMAGE_LINK_PATTERN      = ImagePattern(IMAGE_LINK_RE)
IMAGE_REFERENCE_PATTERN = ImageReferencePattern(IMAGE_REFERENCE_RE)
REFERENCE_PATTERN       = ReferencePattern(REFERENCE_RE)

HTML_PATTERN            = HtmlPattern(HTML_RE)
ENTITY_PATTERN          = HtmlPattern(ENTITY_RE)

AUTOLINK_PATTERN        = AutolinkPattern(AUTOLINK_RE)
AUTOMAIL_PATTERN        = AutomailPattern(AUTOMAIL_RE)


"""
======================================================================
========================== POST-PROCESSORS ===========================
======================================================================

Markdown also allows post-processors, which are similar to
preprocessors in that they need to implement a "run" method. However,
they are run after core processing.

There are two types of post-processors: Postprocessor and TextPostprocessor
"""


class Postprocessor:
    """
    Postprocessors are run before the ElementTree serialization.
    
    Each Postprocessor implements a "run" method that takes a pointer to a
    ElementTree, modifies it as necessary and returns a ElementTree 
    document.
    
    Postprocessors must extend markdown.Postprocessor.

    There are currently no standard post-processors, but the footnote
    extension uses one.
    
    """

    def run(self, root):
        """
        Subclasses of Postprocessor should implement a `run` method, which
        takes a root Element. Method can return another Element, and global
        root Element will be replaced, or just modify current and return None.
        """
        pass



class TextPostprocessor:
    """
    TextPostprocessors are run after the ElementTree it converted back into text.
    
    Each TextPostprocessor implements a "run" method that takes a pointer to a
    text string, modifies it as necessary and returns a text string.
    
    TextPostprocessors must extend markdown.TextPostprocessor.
    
    """

    def run(self, text):
        """
        Subclasses of TextPostprocessor should implement a `run` method, which
        takes the html document as a single text string and returns a 
        (possibly modified) string.

        """
        pass


class RawHtmlTextPostprocessor(TextPostprocessor):
    """ Restore raw html to the document. """
    def __init__(self):
        pass

    def run(self, text):
        """ Iterate over html stash and restore "safe" html. """

        for i in range(self.stash.html_counter):
            html, safe  = self.stash.rawHtmlBlocks[i]
            if self.safeMode and not safe:
                if str(self.safeMode).lower() == 'escape':
                    html = self.escape(html)
                elif str(self.safeMode).lower() == 'remove':
                    html = ''
                else:
                    html = HTML_REMOVED_TEXT
                                   
            text = text.replace("<p>%s\n</p>" % (HTML_PLACEHOLDER % i),
                              html + "\n")
            text =  text.replace(HTML_PLACEHOLDER % i, html)
        return text

    def escape(self, html):
        """ Basic html escaping """
        html = html.replace('&', '&amp;')
        html = html.replace('<', '&lt;')
        html = html.replace('>', '&gt;')
        return html.replace('"', '&quot;')

RAWHTMLTEXTPOSTPROCESSOR = RawHtmlTextPostprocessor()


class AndSubstitutePostprocessor(TextPostprocessor):
    """ Restore valid entities """
    def __init__(self):
        pass

    def run(self, text):

        text =  text.replace(AMP_SUBSTITUTE, "&")
        return text

AMPSUBSTITUTETEXTPOSTPROCESSOR = AndSubstitutePostprocessor()


"""
======================================================================
========================== MISC AUXILIARY CLASSES ====================
======================================================================
"""

class HtmlStash:
    """
    This class is used for stashing HTML objects that we extract
    in the beginning and replace with place-holders.
    """

    def __init__ (self):
        """ Create a HtmlStash. """
        self.html_counter = 0 # for counting inline html segments
        self.rawHtmlBlocks=[]

    def store(self, html, safe=False):
        """
        Saves an HTML segment for later reinsertion.  Returns a
        placeholder string that needs to be inserted into the
        document.

        Keyword arguments:
        
        * html: an html segment
        * safe: label an html segment as safe for safemode
        
        Returns : a placeholder string 
        
        """
        self.rawHtmlBlocks.append((html, safe))
        placeholder = HTML_PLACEHOLDER % self.html_counter
        self.html_counter += 1
        return placeholder
    
    def rest(self):
        self.html_counter = 0
        self.rawHtmlBlocks = []


class BlockGuru:
    """ Parse document for block level constructs (paragraphs, lists, etc.)."""

    def _findHead(self, lines, fn, allowBlank=0):

        """
        Functional magic to help determine boundaries of indented
        blocks.

        Keyword arguments:
        
        * lines: an array of strings
        * fn: a function that returns a substring of a string
           if the string matches the necessary criteria
        * allowBlank: specifies whether it's ok to have blank
           lines between matching functions
        
        Returns: a list of post processes items and the unused
        remainder of the original list
        
        """

        items = []
        item = -1

        i = 0 # to keep track of where we are

        for line in lines:

            if not line.strip() and not allowBlank:
                return items, lines[i:]

            if not line.strip() and allowBlank:
                # If we see a blank line, this _might_ be the end
                i += 1

                # Find the next non-blank line
                for j in range(i, len(lines)):
                    if lines[j].strip():
                        next = lines[j]
                        break
                else:
                    # There is no more text => this is the end
                    break

                # Check if the next non-blank line is still a part of the list

                part = fn(next)

                if part:
                    items.append("")
                    continue
                else:
                    break # found end of the list

            part = fn(line)

            if part:
                items.append(part)
                i += 1
                continue
            else:
                return items, lines[i:]
        else:
            i += 1

        return items, lines[i:]


    def detabbed_fn(self, line):
        """ An auxiliary method to be passed to _findHead """
        m = RE.regExp['tabbed'].match(line)
        if m:
            return m.group(4)
        else:
            return None


    def detectTabbed(self, lines):
        """ Find indented text and remove indent before further proccesing. """
        return self._findHead(lines, self.detabbed_fn,
                              allowBlank = 1)


def dequote(string):
    """ Removes quotes from around a string """
    if ( ( string.startswith('"') and string.endswith('"'))
         or (string.startswith("'") and string.endswith("'")) ):
        return string[1:-1]
    else:
        return string
    
    
class InlineStash:
    
    def __init__(self):
        """ Create a InlineStash. """
        self.prefix = INLINE_PLACEHOLDER_PREFIX
        self.suffix = INLINE_PLACEHOLDER_SUFFIX
        self._nodes = {}
        self.phLength = 4 + len(self.prefix) + len(self.suffix)
        
    def _genPlaceholder(self, type):
        """ Generate a placeholder """
        id = "%04d" % len(self._nodes)
        hash = "%s%s:%s%s" % (self.prefix, type, id, 
                                self.suffix) 
        return hash, id
    
    def extractId(self, data, index):
        """ 
        Extract id from data string, start from index
        
        Keyword arguments:
        
        * data: string
        * index: index, from which we start search 
        
        Returns: placeholder id and  string index, after 
        found placeholder
        """
        endIndex = data.find(self.suffix, index+1)
        if endIndex == -1:
            return None, index + 1 
        else:
            pair = data[index + len(self.prefix): endIndex].split(":")
            if len(pair) == 2:
                return pair[1], endIndex + len(self.suffix)
            else:
                return None, index + 1
    
    def isin(self, id):
        return self._nodes.has_key(id)
    
    def get(self, id):
        """ Return node by id """
        return self._nodes.get(id)
    
    def add(self, node, type):
        """ Add node to stash """
        pholder, id = self._genPlaceholder(type)
        self._nodes[id] = node
        return pholder
    
    def rest(self):
        """ Reset instance """
        self._nodes = {}
    
"""
======================================================================
========================== CORE MARKDOWN =============================
======================================================================

This stuff is hard, so if you are thinking of extending the syntax,
see first if you can do it via pre-processors, post-processors,
inline patterns or a combination of the three.
"""

class CorePatterns:
    """
    This class is scheduled for removal as part of a refactoring effort.
    """

    patterns = {
        'header':          r'(#{1,6})[ \t]*(.*?)[ \t]*(#*)', # # A title
        'reference-def':   r'(\ ?\ ?\ ?)\[([^\]]*)\]:\s*([^ ]*)(.*)',
                           # [Google]: http://www.google.com/
        'containsline':    r'([-]*)$|^([=]*)', # -----, =====, etc.
        'ol':              r'[ ]{0,3}[\d]*\.\s+(.*)', # 1. text
        'ul':              r'[ ]{0,3}[*+-]\s+(.*)', # "* text"
        'isline1':         r'(\**)', # ***
        'isline2':         r'(\-*)', # ---
        'isline3':         r'(\_*)', # ___
        'tabbed':          r'((\t)|(    ))(.*)', # an indented line
        'quoted':          r'[ ]{0,2}> ?(.*)', # a quoted block ("> ...")
    }

    def __init__ (self):

        self.regExp = {}
        for key in self.patterns.keys():
            self.regExp[key] = re.compile("^%s$" % self.patterns[key],
                                          re.DOTALL)

        self.regExp['containsline'] = re.compile(r'^([-]*)$|^([=]*)$', re.M)
        self.regExp['attr'] = re.compile("\{@([^\}]*)=([^\}]*)}") # {@id=123}

RE = CorePatterns()


class Markdown:
    """ 
    Markdown formatter class for creating an html document from Markdown text.
    """


    def __init__(self, 
                 extensions=[],
                 extension_configs={},
                 safe_mode = False):
        """
        Creates a new Markdown instance.

        Keyword arguments:
        
        * extensions: A list of extensions.  
           If they are of type string, the module mdx_name.py will be loaded.  
           If they are a subclass of markdown.Extension, they will be used 
           as-is.
        * extension-configs: Configuration setting for extensions.
        * safe_mode: Disallow raw html. One of "remove", "replace" or "escape".
        
        """

        self.source = None
        self.safeMode = safe_mode
        self.blockGuru = BlockGuru()
        self.registeredExtensions = []
        self.docType = ""
        self.stripTopLevelTags = True

        self.textPreprocessors = [HTML_BLOCK_PREPROCESSOR]

        self.preprocessors = [HEADER_PREPROCESSOR,
                              LINE_PREPROCESSOR,
                              # A footnote preprocessor will
                              # get inserted here
                              REFERENCE_PREPROCESSOR]


        self.postprocessors = [] # a footnote postprocessor will get
                                 # inserted later

        self.textPostprocessors = [# a footnote postprocessor will get
                                   # inserted here
                                   RAWHTMLTEXTPOSTPROCESSOR,
                                   AMPSUBSTITUTETEXTPOSTPROCESSOR]

        self.prePatterns = []
                               
        self.inlinePatterns = [
                               BACKTICK_PATTERN,
                               ESCAPE_PATTERN,
                               REFERENCE_PATTERN,
                               LINK_PATTERN,
                               IMAGE_LINK_PATTERN,
                               IMAGE_REFERENCE_PATTERN,
                               AUTOLINK_PATTERN,
                               AUTOMAIL_PATTERN,
                               LINE_BREAK_PATTERN_2,
                               LINE_BREAK_PATTERN,
                               HTML_PATTERN,
                               ENTITY_PATTERN,
                               NOT_STRONG_PATTERN,
                               STRONG_EM_PATTERN,
                               STRONG_PATTERN,
                               EMPHASIS_PATTERN,
                               EMPHASIS_PATTERN_2
                               # The order of the handlers matters!!!
                               ]
        
        self.inlineStash = InlineStash()
        self.references = {}
        self.htmlStash = HtmlStash()


        self.registerExtensions(extensions = extensions,
                                configs = extension_configs)

        self.reset()


    def registerExtensions(self, extensions, configs):
        """ 
        Register extensions with this instance of Markdown.

        Keyword aurguments:
        
        * extensions: A list of extensions, which can either
           be strings or objects.  See the docstring on Markdown.
        * configs: A dictionary mapping module names to config options. 
        
        """

        for ext in extensions:
            if isinstance(ext, basestring):
                ext = load_extension(ext, configs.get(ext, []))
            elif hasattr(ext, 'extendMarkdown'):
                # Looks like an Extension.
                # Nothing to do here.
                pass
            else:
                message(ERROR, "Incorrect type! Extension '%s' is "
                               "neither a string or an Extension." %(repr(ext)))
                continue
            ext.extendMarkdown(self, globals())

    def registerExtension(self, extension):
        """ This gets called by the extension """
        self.registeredExtensions.append(extension)

    def reset(self):
        """
        Resets all state variables so that we can start with a new text.
        """
        self.inlineStash.rest()
        self.htmlStash.rest()
        self.references.clear()

        HTML_BLOCK_PREPROCESSOR.stash = self.htmlStash
        LINE_PREPROCESSOR.stash = self.htmlStash
        REFERENCE_PREPROCESSOR.references = self.references
        HTML_PATTERN.stash = self.htmlStash
        ENTITY_PATTERN.stash = self.htmlStash
        REFERENCE_PATTERN.references = self.references
        IMAGE_REFERENCE_PATTERN.references = self.references
        RAWHTMLTEXTPOSTPROCESSOR.stash = self.htmlStash
        RAWHTMLTEXTPOSTPROCESSOR.safeMode = self.safeMode

        for extension in self.registeredExtensions:
            extension.reset()

        for pattern in self.inlinePatterns:
            pattern.safe_mode = self.safeMode


    def _transform(self):
        """Transform the Markdown text into a XHTML body document.

        Returns: ElementTree object 
        
        """

        # Setup the document
        
        self.root = etree.Element("span")

        # Split into lines and run the preprocessors that will work with
        # self.lines

        self.lines = self.source.split("\n")

        # Run the pre-processors on the lines
        for prep in self.preprocessors :
            self.lines = prep.run(self.lines)

        # Create a ElementTree from the lines

        buffer = []
        for line in self.lines:
            if line.startswith("#"):

                self._processSection(self.root, buffer)
                buffer = [line]
            else:
                buffer.append(line)

        self._processSection(self.root, buffer)
    
        return etree.ElementTree(self.root)


    def _processSection(self, parent_elem, lines,
                        inList=0, looseList=0):
        """
        Process a section of a source document, looking for high
        level structural elements like lists, block quotes, code
        segments, html blocks, etc.  Some those then get stripped
        of their high level markup (e.g. get unindented) and the
        lower-level markup is processed recursively.

        Keyword arguments:
        
        * parent_elem: A ElementTree element to which the content will be added.
        * lines: a list of lines
        * inList: a level
        
        Returns: None
        
        """
 
        # Loop through lines until none left.
        while lines:
            
            # Skipping empty line
            if not lines[0]:
                lines = lines[1:]
                continue
            
            # Check if this section starts with a list, a blockquote or
            # a code block

            processFn = { 'ul':     self._processUList,
                          'ol':     self._processOList,
                          'quoted': self._processQuote,
                          'tabbed': self._processCodeBlock}

            for regexp in ['ul', 'ol', 'quoted', 'tabbed']:
                m = RE.regExp[regexp].match(lines[0])
                if m:
                    processFn[regexp](parent_elem, lines, inList)
                    return

            # We are NOT looking at one of the high-level structures like
            # lists or blockquotes.  So, it's just a regular paragraph
            # (though perhaps nested inside a list or something else).  If
            # we are NOT inside a list, we just need to look for a blank
            # line to find the end of the block.  If we ARE inside a
            # list, however, we need to consider that a sublist does not
            # need to be separated by a blank line.  Rather, the following
            # markup is legal:
            #
            # * The top level list item
            #
            #     Another paragraph of the list.  This is where we are now.
            #     * Underneath we might have a sublist.
            #

            if inList:

                start, lines  = self._linesUntil(lines, (lambda line:
                                 RE.regExp['ul'].match(line)
                                 or RE.regExp['ol'].match(line)
                                                  or not line.strip()))

                self._processSection(parent_elem, start,
                                     inList - 1, looseList = looseList)
                inList = inList-1

            else: # Ok, so it's just a simple block

                paragraph, lines = self._linesUntil(lines, lambda line:
                                                     not line.strip() or line[0] == '>')

                if len(paragraph) and paragraph[0].startswith('#'):
                    self._processHeader(parent_elem, paragraph)
                    
                elif len(paragraph) and \
                RE.regExp["isline3"].match(paragraph[0]):

                    self._processHR(parent_elem)
                    lines = paragraph[1:] + lines
                    
                elif paragraph:
                    self._processParagraph(parent_elem, paragraph,
                                          inList, looseList)

            if lines and not lines[0].strip():
                lines = lines[1:]  # skip the first (blank) line

    def _processHR(self, parentElem):
        hr = etree.SubElement(parentElem, "hr")
    
    def _processHeader(self, parentElem, paragraph):
        m = RE.regExp['header'].match(paragraph[0])
        if m:
            level = len(m.group(1))
            h = etree.SubElement(parentElem, "h%d" % level)
            h.text = m.group(2).strip()
            #inline = etree.SubElement(h, "inline")
            #inline.text = m.group(2).strip()
        else:
            message(CRITICAL, "We've got a problem header!")


    def _processParagraph(self, parentElem, paragraph, inList, looseList):

        if ( parentElem.tag == 'li'
                and not (looseList or parentElem.getchildren())):

            # If this is the first paragraph inside "li", don't
            # put <p> around it - append the paragraph bits directly
            # onto parentElem
            el = parentElem
        else:
            # Otherwise make a "p" element
            el = etree.SubElement(parentElem, "p")

        dump = []
        
        # Searching for hr or header
        for line in paragraph:
            # it's hr
            if RE.regExp["isline3"].match(line):
                #inline = etree.SubElement(el, "inline")
                #inline.text = "\n".join(dump)
                el.text = "\n".join(dump)
                #etree.SubElement(el, "hr")
                self._processHR(el)
                dump = []
            # it's header
            elif line.startswith("#"):
                #inline = etree.SubElement(el, "inline")
                #inline.text = "\n".join(dump)
                el.text = "\n".join(dump)   
                self._processHeader(parentElem, [line])
                dump = [] 
            else:
                dump.append(line)
        if dump:
            text = "\n".join(dump)    
            #inline = etree.SubElement(el, "inline")
            #inline.text = text
            el.text = text

    def _processUList(self, parentElem, lines, inList):
        self._processList(parentElem, lines, inList,
                         listexpr='ul', tag = 'ul')

    def _processOList(self, parentElem, lines, inList):
        self._processList(parentElem, lines, inList,
                         listexpr='ol', tag = 'ol')


    def _processList(self, parentElem, lines, inList, listexpr, tag):
        """
        Given a list of document lines starting with a list item,
        finds the end of the list, breaks it up, and recursively
        processes each list item and the remainder of the text file.

        Keyword arguments:
        
        * parentElem: A ElementTree element to which the content will be added
        * lines: a list of lines
        * inList: a level
        
        Returns: None
        
        """

        ul = etree.SubElement(parentElem, tag) # ul might actually be '<ol>'

        looseList = 0

        # Make a list of list items
        items = []
        item = -1

        i = 0  # a counter to keep track of where we are

        for line in lines: 

            loose = 0
            if not line.strip():
                # If we see a blank line, this _might_ be the end of the list
                i += 1
                loose = 1

                # Find the next non-blank line
                for j in range(i, len(lines)):
                    if lines[j].strip():
                        next = lines[j]
                        break
                else:
                    # There is no more text => end of the list
                    break

                # Check if the next non-blank line is still a part of the list

                if ( RE.regExp[listexpr].match(next) or
                     RE.regExp['tabbed'].match(next) ):
                    # get rid of any white space in the line
                    items[item].append(line.strip())
                    looseList = loose or looseList
                    continue
                else:
                    break # found end of the list

            # Now we need to detect list items (at the current level)
            # while also detabing child elements if necessary

            for expr in ['ul', 'ol', 'tabbed']:

                m = RE.regExp[expr].match(line)
                if m:
                    if expr in ['ul', 'ol']:  # We are looking at a new item
                        #if m.group(1) :
                        # Removed the check to allow for a blank line
                        # at the beginning of the list item
                        items.append([m.group(1)])
                        item += 1
                    elif expr == 'tabbed':  # This line needs to be detabbed
                        items[item].append(m.group(4)) #after the 'tab'

                    i += 1
                    break
            else:
                items[item].append(line)  # Just regular continuation
                i += 1 # added on 2006.02.25
        else:
            i += 1

        # Add the ElementTree elements
        for item in items:
            li = etree.SubElement(ul, "li")

            self._processSection(li, item, inList + 1, looseList = looseList)

        # Process the remaining part of the section

        self._processSection(parentElem, lines[i:], inList)


    def _linesUntil(self, lines, condition):
        """ 
        A utility function to break a list of lines upon the
        first line that satisfied a condition.  The condition
        argument should be a predicate function.
        
        """

        i = -1
        for line in lines:
            i += 1
            if condition(line): 
                break
        else:
            i += 1
        return lines[:i], lines[i:]

    def _processQuote(self, parentElem, lines, inList):
        """
        Given a list of document lines starting with a quote finds
        the end of the quote, unindents it and recursively
        processes the body of the quote and the remainder of the
        text file.

        Keyword arguments:
        
        * parentElem: ElementTree element to which the content will be added
        * lines: a list of lines
        * inList: a level
        
        Returns: None 
        
        """

        dequoted = []
        i = 0
        blank_line = False # allow one blank line between paragraphs
        for line in lines:
            m = RE.regExp['quoted'].match(line)
            if m:
                dequoted.append(m.group(1))
                i += 1
                blank_line = False
            elif not blank_line and line.strip() != '':
                dequoted.append(line)
                i += 1
            elif not blank_line and line.strip() == '':
                dequoted.append(line)
                i += 1
                blank_line = True
            else:
                break

        blockquote = etree.SubElement(parentElem, "blockquote")

        self._processSection(blockquote, dequoted, inList)
        self._processSection(parentElem, lines[i:], inList)




    def _processCodeBlock(self, parentElem, lines, inList):
        """
        Given a list of document lines starting with a code block
        finds the end of the block, puts it into the ElementTree verbatim
        wrapped in ("<pre><code>") and recursively processes the
        the remainder of the text file.

        Keyword arguments:
        
        * parentElem: ElementTree element to which the content will be added
        * lines: a list of lines
        * inList: a level
        
        Returns: None
        
        """

        detabbed, theRest = self.blockGuru.detectTabbed(lines)

        pre = etree.SubElement(parentElem, "pre")
        code = etree.SubElement(pre, "code")
        
        text = "\n".join(detabbed).rstrip()+"\n"
        code.text = text
        self._processSection(parentElem, theRest, inList)        
        
    def _handleInline(self, data, patternIndex=0):
        """
        Process string with inline patterns and replace it
        with placeholders

        Keyword arguments:
        
        * data: A line of Markdown text
        * patternIndex: The index of the inlinePattern to start with
        
        Returns: String with placeholders. 
        
        """
        if isinstance(data, AtomicString):
            return data
        
        startIndex = 0
        
        while patternIndex < len(self.inlinePatterns):
            
            data, matched, startIndex = self._applyInline(
                                             self.inlinePatterns[patternIndex],
                                             data, patternIndex, startIndex)
            
            if not matched:
                patternIndex += 1

        return data
    
    def _applyInline(self, pattern, data, patternIndex, startIndex=0):
        """ 
        Check if the line fits the pattern, create the necessary 
        elements, add it to InlineStash
        
        Keyword arguments:
        
        * data: the text to be processed
        * pattern: the pattern to be checked
        * patternIndex: index of current pattern
        * startIndex: string index, from which we starting search

        Returns: String with placeholders instead of ElementTree elements.
        """
        
        match = pattern.getCompiledRegExp().match(data[startIndex:])
        leftData = data[:startIndex]
 
        if not match:
            return data, False, 0

        node = pattern.handleMatch(match)
     
        if node is None:
            return data, True, len(leftData) + match.span(len(match.groups()))[0]
        
        if not isstr(node):            
            if not node.tag in ["code", "pre"]:
                # We need to process current node too
                for child in [node] + node.getchildren():
                    if not isstr(node):
                        if child.text:
                            child.text = self._handleInline(child.text, 
                                                            patternIndex + 1)
                        if child.tail:
                            child.tail = self._handleInline(child.tail, 
                                                            patternIndex)
   
        pholder = self.inlineStash.add(node, pattern.type())

        return "%s%s%s%s" % (leftData, 
                             match.group(1), 
                             pholder, match.groups()[-1]), True, 0
   
    def _processElementText(self, node, subnode, isText=True):
        """
        Process placeholders in Element.text or Element.tail
        of Elements popped from InlineStash
        
        Keywords arguments:
        
        * node: parent node
        * subnode: processing node
        * isText: bool variable, True - it's text, False - it's tail
        
        Returns: None
        
        """       
        if isText:
            text = subnode.text
            subnode.text = None
        else:
            text = subnode.tail
            subnode.tail = None
        
        childResult = self._processPlaceholders(text, subnode)
        
        if not isText and node is not subnode:
            pos = node.getchildren().index(subnode)
            node.remove(subnode)
        else:
            pos = 0
            
        childResult.reverse()
        for newChild in childResult:
            node.insert(pos, newChild)
    
    def _processPlaceholders(self, data, parent):
        """
        Process string with placeholders and generate ElementTree tree.
        
        Keyword arguments:
        
        * data: string with placeholders instead of ElementTree elements.
        * parent: Element, which contains processing inline data

        Returns: list with ElementTree elements with applied inline patterns.
        """
        
        def linkText(text):
            if text:
                if result:
                    if result[-1].tail:
                        result[-1].tail += text
                    else:
                        result[-1].tail = text
                else:
                    if parent.text:
                        parent.text += text
                    else:
                        parent.text = text
            
        result = []
        prefix = self.inlineStash.prefix
        strartIndex = 0
    
        while data:
            
            index = data.find(prefix, strartIndex)
            if index != -1:
                
                id, phEndIndex = self.inlineStash.extractId(data, index)
                
                if self.inlineStash.isin(id):
   
                    node = self.inlineStash.get(id)
             
                    if index > 0:
                        text = data[strartIndex:index]
                        linkText(text)
          
                    if not isstr(node): # it's Element
                        
                        for child in [node] + node.getchildren():
            
                            if child.tail:
                                if child.tail.strip():
                                    self._processElementText(node, child, False)
                            
                            if child.text:
                                if child.text.strip():
                                    self._processElementText(child, child)
                        
                    else: # it's just a string
                
                        linkText(node)
                        strartIndex = phEndIndex
                        continue
                    
                    strartIndex = phEndIndex    
                    result.append(node)
                       
                else: # wrong placeholder
                    end = index + len(prefix)
                    linkText(data[strartIndex:end])
                    strartIndex = end 
            else:
                
                text = data[strartIndex:]
                linkText(text)
                data = ""

        return result
    
    
    def applyInlinePatterns(self, markdownTree):
        """
        Iterate over ElementTree, find elements with inline tag, 
        apply inline patterns and append newly created Elements to tree 
        
        Keyword arguments:
        
        * markdownTree: ElementTree object, representing Markdown tree.

        Returns: ElementTree object with applied inline patterns.
        """
 
        el = markdownTree.getroot()
                
        stack = [el]

        while stack:
            currElement = stack.pop()
            insertQueue = []
            for child in currElement.getchildren():
                
            #if child.tag == "inline":
                if not isinstance(child.text, AtomicString) and child.text \
                and not child.tag in ["code", "pre"]:
                    
                    text = child.text
                    child.text = None
                    lst = self._processPlaceholders(self._handleInline(
                                                    text), child)
                    stack += lst
                    

                    insertQueue.append((child, lst))
                    
                
                if child.getchildren():
                    stack.append(child) 

                      
            for element, lst in insertQueue:
                #currElement.remove(element)
                if element.text:
                    element.text = handleAttributes(element.text, 
                                                        element)
                i = 0
                for newChild in lst:
                    # Processing attributes
                    if newChild.tail:
                        newChild.tail = handleAttributes(newChild.tail, 
                                                         element)
                    if newChild.text:
                        newChild.text = handleAttributes(newChild.text, 
                                                         newChild)
                    element.insert(i, newChild)
                    i += 1
               
            
        return markdownTree

        
    def markdownToTree(self, source=None):
        """
        Create ElementTree, without applying inline paterns, 
        all data, include all data, that must be procesed wit inline 
        patterns in <inline></inline> sections.
        
        Keyword arguments:
        
        * source: An ascii or unicode string of Markdown formated text.

        Returns: ElementTree object.
        """
        if source is not None: #Allow blank string
            self.source = source
            
        if not self.source:
            return u""
        
        try:
            self.source = unicode(self.source)
        except UnicodeDecodeError:
            message(CRITICAL, 'UnicodeDecodeError: Markdown only accepts unicode or ascii  input.')
            return u""
        
        # Fixup the source text

        self.source = self.source.replace(STX, "")
        self.source = self.source.replace(ETX, "")

        self.source = self.source.replace("\r\n", "\n").replace("\r", "\n")
        self.source += "\n\n"
        self.source = self.source.expandtabs(TAB_LENGTH)

        for pp in self.textPreprocessors:
            self.source = pp.run(self.source)
        
        markdownTree = self._transform()
        
        return markdownTree      

    def convert (self, source=None):
        """
        Create the document in XHTML format.

        Keyword arguments:
        
        * source: An ascii or unicode string of Markdown formated text.

        Returns: A serialized XHTML body.

        """

        tree = self.markdownToTree(source)

        root = self.applyInlinePatterns(tree).getroot()

        # Run the post-processors
        for postprocessor in self.postprocessors:
            postprocessor.stash = self.htmlStash
            newRoot = postprocessor.run(root)
            if newRoot:
                root = newRoot

        indentETree(root)

        xml, length = codecs.utf_8_decode(etree.tostring(root, encoding="utf8"))
        
        if self.stripTopLevelTags:
            xml = xml.strip()[44:-7] + "\n"

        # Run the text post-processors
        for pp in self.textPostprocessors:
            xml = pp.run(xml)

        return xml.strip()


    def __str__(self):
        ''' Report info about instance. Markdown always returns unicode. '''

        if self.source is None:
            status = 'in which no source text has been assinged.'
        else:
            status = 'which contains %d chars and %d line(s) of source.'%\
                     (len(self.source), self.source.count('\n')+1)
        return 'An instance of "%s" %s'% (self.__class__, status)

    __unicode__ = convert # markdown should always return a unicode string





# ====================================================================

def markdownFromFile(input = None,
                     output = None,
                     extensions = [],
                     encoding = None,
                     message_threshold = CRITICAL,
                     safe = False):
    """
    Convenience wrapper function that takes a filename as input.

    Used from the command-line, although may be useful in other situations. 
    Decodes the file using the provided encoding (defaults to utf-8), passes 
    the file content to markdown, and outputs the html to either the provided
    filename or stdout in the same encoding as the source file.

    **Note:** This is the only place that decoding and encoding takes place
    in Python-Markdown.

    Keyword arguments:

    * input: Name of source text file.
    * output: Name of output file. Writes to stdout if `None`.
    * extensions: A list of extension names (may contain config args).  
    * encoding: Encoding of input and output files. Defaults to utf-8.
    * message_threshold: Error reporting level.
    * safe_mode: Disallow raw html. One of "remove", "replace" or "escape".

    Returns: An HTML document as a string.

    """

    global console_hndlr
    console_hndlr.setLevel(message_threshold)

    message(DEBUG, "input file: %s" % input)

    if not encoding:
        encoding = "utf-8"

    input_file = codecs.open(input, mode="r", encoding=encoding)
    text = input_file.read()
    input_file.close()

    text = removeBOM(text, encoding)

    new_text = markdown(text, extensions, safe_mode = safe)

    if output:
        output_file = codecs.open(output, "w", encoding=encoding)
        output_file.write(new_text)
        output_file.close()

    else:
        sys.stdout.write(new_text.encode(encoding))

def markdown(text,
             extensions = [],
             safe_mode = False):
    """
    Convenience wrapper function for `Markdown` class.

    Useful in a typical use case. Initializes an instance of the `Markdown` 
    class, loads any extensions and runs the parser on the given text. 

    Keyword arguments:

    * text: An ascii or Unicode string of Markdown formatted text.
    * extensions: A list of extension names (may contain config args).  
    * safe_mode: Disallow raw html. One of "remove", "replace" or "escape".

    Returns: An HTML document as a string.

    """
    message(DEBUG, "in markdown.markdown(), received text:\n%s" % text)

    extensions = [load_extension(e) for e in extensions]

    md = Markdown(extensions=extensions,
                  safe_mode = safe_mode)

    return md.convert(text)
        

class Extension:
    """ Base class for extensions to subclass. """
    def __init__(self, configs = {}):
        """ 
        Create an instance of an Extention. 
        
        Keyword arguments:

        * configs: A dict of configuration setting used by an Extension.
        """
        self.config = configs

    def getConfig(self, key):
        """ Return a setting for the given key or an empty string. """
        if self.config.has_key(key):
            return self.config[key][0]
        else:
            return ""

    def getConfigInfo(self):
        """ Return all config settings as a list of tuples. """
        return [(key, self.config[key][1]) for key in self.config.keys()]

    def setConfig(self, key, value):
        """ Set a config setting for `key` with the given `value`. """
        self.config[key][0] = value

    def extendMarkdown(self, md, md_globals):
        """ 
        Add the various proccesors and patterns to the Markdown Instance. 
        
        This method must be overriden by every extension.

        Ketword arguments:

        * md: The Markdown instance.

        * md_globals: All global variables availabel in the markdown module
        namespace.

        """
        pass


def load_extension(ext_name, configs = []):
    """ 
    Load extension by name, then return the module.
    
    The extension name may contain arguments as part of the string in the 
    following format:

        "extname(key1=value1,key2=value2)"
    
    Print an error message and exit on failure. 
    
    """

    # I am making the assumption that the order of config options
    # does not matter.
    configs = dict(configs)
    pos = ext_name.find("(") 
    if pos > 0:
        ext_args = ext_name[pos+1:-1]
        ext_name = ext_name[:pos]
        pairs = [x.split("=") for x in ext_args.split(",")]
        configs.update([(x.strip(), y.strip()) for (x, y) in pairs])

    ext_module = 'markdown_extensions'
    module_name = '.'.join([ext_module, ext_name])
    extension_module_name = '_'.join(['mdx', ext_name])

    try:
            module = __import__(module_name, {}, {}, [ext_module])
    except ImportError:
        try:
            module = __import__(extension_module_name)
        except:
            message(WARN,
                "Failed loading extension '%s' from '%s' or '%s' "
                "- continuing without."
                % (ext_name, module_name, extension_module_name) )
            # Return a dummy (do nothing) Extension as silent failure
            return Extension(configs={})

    return module.makeExtension(configs.items())    


OPTPARSE_WARNING = """
Python 2.3 or higher required for advanced command line options.
For lower versions of Python use:

      %s INPUT_FILE > OUTPUT_FILE
    
""" % EXECUTABLE_NAME_FOR_USAGE

def parse_options():
    """
    Define and parse `optparse` options for command-line usage.
    """

    try:
        optparse = __import__("optparse")
    except:
        if len(sys.argv) == 2:
            return {'input': sys.argv[1],
                    'output': None,
                    'message_threshold': CRITICAL,
                    'safe': False,
                    'extensions': [],
                    'encoding': None }

        else:
            print OPTPARSE_WARNING
            return None

    parser = optparse.OptionParser(usage="%prog INPUTFILE [options]")

    parser.add_option("-f", "--file", dest="filename",
                      help="write output to OUTPUT_FILE",
                      metavar="OUTPUT_FILE")
    parser.add_option("-e", "--encoding", dest="encoding",
                      help="encoding for input and output files",)
    parser.add_option("-q", "--quiet", default = CRITICAL,
                      action="store_const", const=60, dest="verbose",
                      help="suppress all messages")
    parser.add_option("-v", "--verbose",
                      action="store_const", const=INFO, dest="verbose",
                      help="print info messages")
    parser.add_option("-s", "--safe", dest="safe", default=False,
                      metavar="SAFE_MODE",
                      help="safe mode ('replace', 'remove' or 'escape'  user's HTML tag)")
    
    parser.add_option("--noisy",
                      action="store_const", const=DEBUG, dest="verbose",
                      help="print debug messages")
    parser.add_option("-x", "--extension", action="append", dest="extensions",
                      help = "load extension EXTENSION", metavar="EXTENSION")

    (options, args) = parser.parse_args()

    if not len(args) == 1:
        parser.print_help()
        return None
    else:
        input_file = args[0]

    if not options.extensions:
        options.extensions = []

    return {'input': input_file,
            'output': options.filename,
            'message_threshold': options.verbose,
            'safe': options.safe,
            'extensions': options.extensions,
            'encoding': options.encoding }

def main():
    """ Run Markdown from the command line. """

    options = parse_options()

    if not options:
        sys.exit(0)
    
    markdownFromFile(**options)

if __name__ == '__main__':
    main()
