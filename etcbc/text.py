import collections
from .lib import Transcription
from .blang import booklangs, booknames

def h_esc(x): return x.replace('&', '&amp;').replace('<', '&lt;')

class Text(object):
    '''Text representations
    '''
    def __init__(self, lafapi):
        lafapi.api['fabric'].load_again({"features": ('''
            otype
            g_word_utf8 trailer_utf8
            g_qere_utf8 qtrailer_utf8
            lex_utf8
            phono phono_sep
            book chapter verse
''', '')}, annox='lexicon', add=True, verbose='INFO')
        self._verses = lafapi.data_items['zV00(verses)']
        self.lafapi = lafapi
        self.env = lafapi.names.env
        F = lafapi.api['F']
        self.transcription = Transcription()

        def get_orig(w):
            word = F.g_word_utf8.v(w)
            qere = F.g_qere_utf8.v(w)
            if qere == None:
                orig = word
                trl = F.trailer_utf8.v(w)
            else:
                orig = qere
                trl = F.qtrailer_utf8.v(w)
            origt = self.transcription.from_hebrew(orig + trl).replace('_', ' ')
            return origt

        def get_orig_p(w):
            s = F.phono_sep.v(w)
            if '.' in s: s += '\n'
            return F.phono.v(w)+s

        self._transform = collections.OrderedDict((
            ('hp', ('hebrew primary', lambda w: F.g_word_utf8.v(w)+F.trailer_utf8.v(w))),
            ('ha', ('hebrew accent',  lambda w: Transcription.to_hebrew(get_orig(w)))),
            ('hv', ('hebrew vowel',   lambda w: Transcription.to_hebrew_v(get_orig(w)))),
            ('hc', ('hebrew cons',    lambda w: Transcription.to_hebrew_c(get_orig(w)))),
            ('ea', ('trans accent',   lambda w: get_orig(w))),
            ('ev', ('trans vowel',    lambda w: Transcription.to_etcbc_v(get_orig(w)))),
            ('ec', ('trans cons',     lambda w: Transcription.to_etcbc_c(get_orig(w)))),
            ('pf', ('phono full',     lambda w: get_orig_p(w).replace('*',''))),
            ('ps', ('phono simple',   lambda w: Transcription.ph_simplify(get_orig_p(w)))),
        ))
        self._books = lafapi.data_items['zV00(books_la)']
        self.book_nodes = tuple(x[0] for x in self._books)
        self._book_name = {}
        self._book_node = {}
        self.langs = booklangs
        self.booknames = booknames
        for (bn, book_la) in self._books:
            self._book_name.setdefault('la', {})[bn] = book_la
            self._book_node.setdefault('la', {})[book_la] = bn
        for ln in self.booknames:
            for (i, (bn, book_la)) in enumerate(self._books):
                book_ln = self.booknames[ln][i]
                self._book_name.setdefault(ln, {})[bn] = book_ln
                self._book_node.setdefault(ln, {})[book_ln] = bn

    def node_of(self, book, chapter, verse, lang='en'):
        book_node = self._book_node.get(lang, {}).get(book, None)
        return self._verses.get(book_node, {}).get(chapter, {}).get(verse, None)

    def formats(self): return self._transform

    def book_name(self, bn, lang='en'): return self._book_name.get(lang, {}).get(bn, None)
    def book_node(self, book_name, lang='en'): return self._book_node.get(lang, {}).get(book_name, None)
             
    def words(self, wnodes, fmt='ha'):
        reps = []
        fmt = fmt if fmt in self._transform else 'ha'
        make_rep = self._transform[fmt][1]
        for wnode in wnodes: reps.append(make_rep(wnode))
        return ''.join(reps)

    def text(self, book=None, chapter=None, verse=None, fmt='ha', html=False, verse_label=True, lang='en', style=None):
        L = self.lafapi.api['L']
        F = self.lafapi.api['F']
        msg = self.lafapi.api['msg']
        tables = []
        txt = []
        bks = [] if book == None else [book] if type(book) is str else list(book)
        chs = [] if chapter == None else [chapter] if type(chapter) is int else list(chapter)
        vss = [] if verse == None else [verse] if type(verse) is int else list(verse)

        def dump_table():
            if html:
                tables.append('<table class="t">\n{}</table>\n\n'.format(''.join(txt)))
            else:
                tables.append(''.join(txt))
            txt.clear()
            
        if book == None: book_nodes = tuple(x[0] for x in self._books)
        else:
            book_nodes = []
            for bk in bks:
                bn = self._book_node.get(lang, {}).get(bk, None)
                if bn == None:
                    msg('No book named "{}" in language "{}"'.format(bk, lang))
                    continue
                book_nodes.append(bn)
        for bn in book_nodes:
            bkname = self.book_name(bn, lang) 
            cnodes = L.d('chapter', bn)
            if len(chs) == 0: chapter_nodes = cnodes
            else:
                chapter_nodes = []
                for ch in chs:
                    if ch not in self._verses[bn]:
                        msg('No chapter {} in book "{}" ({})'.format(ch, bkname, lang))
                    else:
                        chapter_nodes.extend([c for c in cnodes if int(F.chapter.v(c)) == ch])
            for cn in chapter_nodes:
                chname = F.chapter.v(cn)
                vnodes = L.d('verse', cn)
                if len(vss) == 0: verse_nodes = vnodes
                else: 
                    verse_nodes = []
                    for vs in vss:
                        if vs not in self._verses[bn][int(chname)]:
                            msg('No verse {} in book "{}" ({}) chapter {}'.format(vs, bkname, lang, chname))
                        else:
                            verse_nodes.extend([v for v in vnodes if int(F.verse.v(v)) == vs])
                for vn in verse_nodes:
                    vsname = F.verse.v(vn)
                    vslabel = '{} {}:{}'.format(bkname,chname,vsname)
                    vshead = '' if not verse_label else '<td class="vl">{}</td>'.format(vslabel) if html else '{}\t'.format(vslabel)
                    tx = self.words(L.d('word', vn), fmt=fmt)
                    if html: tx = '<td class="{}">{}</td>'.format(fmt[0], h_esc(tx))
                    line = '<tr>{}{}</tr>\n'.format(vshead, tx) if html else vshead + tx.rstrip('\n')+'\n'
                    txt.append(line)

                if len(vss) != 1: dump_table()
            if len(vss) == 1 and len(chs) != 1: dump_table()
        if len(vss) == 1 and len(chs) == 1: dump_table()
        body = ''.join(tables)
        if not style or not html:
            return body
        else:
            title = '{} {}:{} [{}]'.format(
                ', '.join(str(bk) for bk in bks) if book != None else 'all books',
                ', '.join(str(ch) for ch in chs) if chapter != None else 'all chapters',
                ', '.join(str(vs) for vs in vss) if verse != None else 'all verses',
                fmt,
            )
            return '''<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<title>{}</title>
{}
</head>
<body>
{}
</body>
</html>
'''.format(title, style, body)

    def style(self, params=None, show_params=False):
        msg = self.lafapi.api['msg']
        style_defaults = dict(
            hebrew_color='000000',
            hebrew_size='large',
            hebrew_line_height='1.8',
            etcbc_color='aa0066',
            etcbc_size='small',
            etcbc_line_height='1.5',
            phono_color='00b040',
            phono_size='medium',
            phono_line_height='1.5',
            verse_color='0000ff',
            verse_size='small',
            verse_width='5em',
        )
        errors = []
        good = True
        for x in [1]:
            good = False
            if params == None:
                params = dict()
            if type(params) is not dict:
                errors.append('ERROR: the style parameters should be a dictionary')
                break
            thisgood = True
            for x in params:
                if x not in style_defaults:
                    errors.append('ERROR: unknown style parameter: {}'.format(x))
                    thisgood = False
            if not thisgood: break
            good = True
        if not good:
            errors.append('ERROR: wrong style specfication. Switching to default values')
            for e in errors: msg(e)
            params = dict()
        style_defaults.update(params)
        if not good or show_params:
            for x in sorted(style_defaults): msg('{} = {}'.format(x, style_defaults[x]))

        return '''
<style type="text/css">
table.t {{
    width: 100%;
}}
td.h {{
    font-family: Ezra SIL, SBL Hebrew, Verdana, sans-serif;
    font-size: {hebrew_size};
    line-height: {hebrew_line_height};
    color: #{hebrew_color};
    text-align: right;
    direction: rtl;
}}
td.e {{
    font-family: Menlo, Courier New, Courier, monospace;
    font-size: {etcbc_size};
    line-height: {etcbc_line_height};
    color: #{etcbc_color};
    text-align: left;
    direction: ltr;
}}
td.p {{
    font-family: Verdana, Arial, sans-serif;
    font-size: {phono_size};
    line-height: {phono_line_height};
    color: #{phono_color};
    text-align: left;
    direction: ltr;
}}

td.vl {{
    font-family: Verdana, Arial, sans-serif;
    font-size: {verse_size};
    text-align: right;
    vertical-align: top;
    color: #{verse_color};
    width: {verse_width};
    direction: ltr;
}}
</style>
'''.format(**style_defaults)