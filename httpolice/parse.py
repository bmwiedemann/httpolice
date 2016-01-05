# -*- coding: utf-8; -*-

class Ignore(object):

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Ignore(%r)' % self.value


class ParseError(Exception):

    pass


class MismatchError(ParseError):

    def __init__(self, pos, expected, found):
        super(MismatchError, self).__init__(
            u'at byte position %d: expected %s - found %r' %
            (pos, expected, found))
        self.pos = pos
        self.expected = expected
        self.found = found


class State(object):

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.stack = []

    def push(self):
        self.stack.append(self.pos)

    def pop(self):
        self.pos = self.stack.pop()

    def discard(self):
        self.stack.pop()

    def is_eof(self):
        return self.pos >= len(self.data)

    def consume(self, s):
        if self.data[self.pos : self.pos + len(s)] == s:
            self.pos += len(s)
            return True
        else:
            return False

    def peek(self, n=1):
        return self.data[self.pos : self.pos + n]


class Parser(object):

    def parse(self, state):
        raise NotImplementedError

    def __or__(self, other):
        return AlternativeParser([self, other])

    def __add__(self, other):
        return SequenceParser([self, other])


class NoOpParser(Parser):

    def __repr__(self):
        return 'NoOpParser()'

    def parse(self, state):
        return ''


class NamedParser(Parser):

    def __init__(self, name, inner):
        super(NamedParser, self).__init__()
        self.name = name
        self.inner = inner

    def parse(self, state):
        pos = state.pos
        try:
            return self.inner.parse(state)
        except MismatchError, e:
            if e.pos == pos:
                raise MismatchError(e.pos, self.name, e.found)
            else:
                raise


class LiteralParser(Parser):

    def __init__(self, s):
        super(LiteralParser, self).__init__()
        self.literal = s

    def __repr__(self):
        return 'LiteralParser(%r)' % self.literal

    def parse(self, state):
        if state.consume(self.literal):
            return self.literal
        else:
            raise MismatchError(state.pos, u'%r' % self.literal,
                                state.peek(len(self.literal)))


class CharClassParser(Parser):

    def __init__(self, chars):
        super(CharClassParser, self).__init__()
        self.chars = chars

    def __repr__(self):
        return 'CharClassParser(%r)' % self.chars

    def parse(self, state):
        c = state.peek()
        if c and (c in self.chars):
            state.consume(c)
            return c
        else:
            raise MismatchError(state.pos, u'one of %r' % self.chars, c)


class SequenceParser(Parser):

    def __init__(self, inners):
        super(SequenceParser, self).__init__()
        self.inners = inners

    def __repr__(self):
        return 'SequenceParser(%r)' % self.inners

    def parse(self, state):
        rs = []
        for inner in self.inners:
            r = inner.parse(state)
            if not isinstance(r, Ignore):
                rs.append(r)
        if len(rs) == 1:
            return rs[0]
        else:
            return tuple(rs)

    def __add__(self, other):
        return SequenceParser(self.inners + [other])


class AlternativeParser(Parser):

    def __init__(self, inners):
        super(AlternativeParser, self).__init__()
        self.inners = inners

    def __repr__(self):
        return 'AlternativeParser(%r)' % self.inners

    def parse(self, state):
        errors = []
        for inner in self.inners:
            state.push()
            try:
                r = inner.parse(state)
            except ParseError, e:
                state.pop()
                errors.append(e)
            else:
                state.discard()
                return r
        else:
            max_pos = max(e.pos for e in errors)
            best_errors = sorted((e for e in errors if e.pos == max_pos),
                                 key=lambda e: len(e.found), reverse=True)
            raise MismatchError(max_pos,
                                u' or '.join(e.expected for e in best_errors),
                                best_errors[0].found)

    def __or__(self, other):
        return AlternativeParser(self.inners + [other])


class TimesParser(Parser):

    def __init__(self, inner, min_=None, max_=None):
        super(TimesParser, self).__init__()
        self.inner = inner
        self.min_ = min_
        self.max_ = max_

    def __repr__(self):
        return 'TimesParser(%r, %r, %r)' % (self.inner, self.min_, self.max_)

    def parse(self, state):
        r = []
        while (self.max_ is None) or (len(r) < self.max_):
            state.push()
            try:
                r.append(self.inner.parse(state))
            except ParseError:
                state.pop()
                if (self.min_ is None) or (len(r) >= self.min_):
                    return r
                else:
                    raise
            else:
                state.discard()
        return r


class WrapParser(Parser):

    def __init__(self, func, inner):
        super(WrapParser, self).__init__()
        self.func = func
        self.inner = inner

    def __repr__(self):
        return 'WrapParser(%r, %r)' % (self.func, self.inner)

    def parse(self, state):
        return self.func(self.inner.parse(state))


wrap = WrapParser
ignore = lambda inner: wrap(Ignore, inner)
maybe = lambda inner: inner | NoOpParser()
literal = LiteralParser
char_class = CharClassParser
times = lambda min_, max_, inner: TimesParser(inner, min_, max_)
many = lambda inner: TimesParser(inner, min_=0)
many1 = lambda inner: TimesParser(inner, min_=1)
join = lambda inner: wrap(''.join, inner)
string = lambda inner: join(many(inner))
string1 = lambda inner: join(many1(inner))
named = NamedParser
rfc = lambda n, name, inner: named(u'<%s> (RFC %d)' % (name, n), inner)
decode = lambda inner: wrap(lambda s: s.decode('utf-8', 'replace'), inner)
decode_into = lambda con, inner: wrap(con, decode(inner))

char_range = lambda min_, max_: ''.join(chr(x) for x in range(min_, max_ + 1))
