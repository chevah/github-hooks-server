

import sqlite3
from re import split
from itertools import groupby, count
from operator import itemgetter

from datetime import timedelta, datetime
from epsilon.extime import Time
from epsilon import structlike

linkStyle = "text-decoration: none; color: white;"

from twisted.web.template import Element, XMLFile, renderer, tags, flatten

from twisted.python.modules import getModule
from twisted.python.filepath import FilePath


CONFIGURATION = {
    'trac-db': ('no/such/path/define-a-trac-db',),
    }


factors = {}

class Factor(structlike.record('order points description')):
    """
    A score thing.
    """

_nextorder = count().next

def deffactor(score, description):
    """
    Define a new factor with an associated score and textual english
    description.

    Suck it, ubuntu.  Use software in ENGLISH.
    """
    key = (object(), repr(description))
    factors[key] = Factor(_nextorder(), score, description)
    return key

# You can enter tags (tags.br()) in the description as this is sent to HTML.
DONE_REVIEW = deffactor(200, "complete a review")
NEEDS_REVIEW = deffactor(75, "submitting a ticket for review")
FIXED = deffactor(75, "solving a ticket")
JUST_CLOSED = deffactor(25, "closing a ticket without solving it")
CREATE_TICKET = deffactor(15, "creating a ticket")
JUST_COMMENT = deffactor(10, "leaving a comment or updating the description")

# How many points to get for each action from that month.
ACTION_POINTS_RATIO = 0.1

here = FilePath(__file__)

class HiscoresPage(Element):
    loader = XMLFile(here.sibling('static').child('highscores.html').open())

    def __init__(self, dateWithinMonth, scores):
        self.dateWithinMonth = dateWithinMonth
        self.allScores = scores


    def linkTag(self, time, arrowDirection, hidden=False):
        style = linkStyle
        if hidden:
            style += ' visibility: hidden;'
        return tags.a(
            style=style,
            href="?time=%s" % (time.asDatetime().strftime('%Y-%m-%d'),)
        )(
            tags.img(
                border="0",
                src="hooks-static/%s-arrow.png" % (arrowDirection,),
                )
        )


    @renderer
    def next(self, request, tag):
        start, end = monthRangeAround(self.dateWithinMonth + timedelta(days=45))
        hidden = False
        if start > Time():
            hidden = True
        return tag(self.linkTag(start, "right", hidden))


    @renderer
    def previous(self, request, tag):
        start, end = monthRangeAround(self.dateWithinMonth - timedelta(hours=1))
        return tag(self.linkTag(start, "left"))


    @renderer
    def scores(self, request, oneRowTag):
        for pos, (score, author) in enumerate(self.allScores):
            pos += 1
            if pos == 1:
                color = 'yellow'
            elif pos == 2:
                color = 'white'
            elif pos == 3:
                color = 'orange'
            else:
                if pos > 10:
                    color = '#555555'
                else:
                    color = '#888888'
            rank = str(pos)
            if (pos % 100) > 10 and (pos % 100) < 20:
                suffix = 'th'
            elif rank[-1] == '1':
                suffix = 'st'
            elif rank[-1] == '2':
                suffix = 'nd'
            elif rank[-1] == '3':
                suffix = 'rd'
            else:
                suffix = 'th'
            yield oneRowTag.clone().fillSlots(rank=str(pos) + suffix,
                                              color=color,
                                              bang="!" * max(0, 4-pos),
                                              total=str(score),
                                              author=author)


    @renderer
    def action_points_ratio(self, request, tag):
        return tag(str(ACTION_POINTS_RATIO))

    @renderer
    def footer(self, request, tag):
        for factor in sorted(factors.values(), key=lambda f: f.order):
            tag(str(factor.points), " points for ", factor.description, tags.br())
        return tag


def render(output, rangeStart, scores):
    """
    Write some score data to a callable of some kind.

    @param rangeStart: A L{Time} instance giving the beginning of the time range
        containing the given scores.

    @param scores: the scores data structure as returned by getscores.

    @param output: a callable that takes a C{str}; call it repeatedly to write
        the output.
    """
    page = HiscoresPage(rangeStart, scores)
    # Not requesting any asynchronous data, so we can just ignore the result of
    # this Deferred.
    flatten(None, page, output)


def getscores(actions):
    """
    Calculate each author's scores from the given month of actions.
    """
    tiebreaker = count()
    scores = {}
    for (action, ticket, author, time) in actions:
        scores[author] = (scores.get(author, 0) + factors[action].points +
                          tiebreaker.next()* ACTION_POINTS_RATIO)

    # The scores are rounded by conversion to `int`.
    return sorted(
        [(int(score), author) for (author, score) in scores.items()],
        reverse=True,
        )


def parsetime(s):
    y, m, d = map(int, s.split("-"))
    return Time.fromDatetime(datetime(year=y, month=m, day=d))



HOW_LONG_IS_A_MONTH_I_DONT_KNOW = 27

def monthRangeAround(t):
    beginningdt = t.asDatetime().replace(day=1, hour=0, minute=0, second=0,
                                         microsecond=0)
    td = timedelta(days=HOW_LONG_IS_A_MONTH_I_DONT_KNOW)
    while (beginningdt + td).month == beginningdt.month:
        td += timedelta(days=1)
    beginning = Time.fromDatetime(beginningdt)
    end = Time.fromDatetime(beginningdt + td)
    return (beginning, end)


def getChanges(start, end):
    con = sqlite3.connect(*CONFIGURATION['trac-db'])
    try:
        cur = con.cursor()
        cur.execute("""
            select ticket, (time / 1000000), author, field, oldvalue, newvalue
            from
                ticket_change
            where
                (time / 1000000) > %s and (time / 1000000) < %s
            order by
                time asc
            """ % (start.asPOSIXTimestamp(), end.asPOSIXTimestamp()))

        return cur.fetchall()
    finally:
        con.close()

def getOwnser(id):
    """
    Return the current owner for ticket with `id`.
    """
    con = sqlite3.connect(*CONFIGURATION['trac-db'])
    try:
        cur = con.cursor()
        cur.execute('select owner from ticket where id = %s' % (id,))
        result = cur.fetchall()
        owner = result[0][0]
        if not owner:
            owner = 'UNKNOWN'
        return owner
    finally:
        con.close()

def splitKeywords(keywords):
    if keywords is None:
        return []
    return filter(None, split('[ ,]', keywords))


def getActions(changes):
    """
    Compute the actions represented by the given sequence of ticket change rows.

    @param changes: A sequence of changes from a trac ticket_change table,
    ordered by time (so as to be able to detect which change rows are part of
    the same logical change).
    """
    lastReview = {} # map ticket(int): username of last reviewer (unicode-ish)

    for time, localChanges in groupby(changes, itemgetter(1)):
        actions = []
        comment = None
        for ticket, time, author, field, oldvalue, newvalue in localChanges:
            author = author.lower()

            if field == 'resolution':
                # Ticket was closed.
                if newvalue == 'fixed':
                    if author == 'pqm':
                        # This is closed by PQM but we track this via the
                        # PQM comment.
                        continue
                    else:
                        # Mark to discover the actual author.
                        actions.append((FIXED, author))
                else:
                    actions.append((JUST_CLOSED, author))

            elif field == 'comment':
                # An action was done to the ticket.
                comment = newvalue

                if author == 'pqm':
                    if comment.startswith('Branch landed on master.'):
                        # The informative comment from PQM that the
                        # ticket was closed.
                        # We get the owner from the ticket owner.
                        author = getOwnser(ticket)
                    else:
                        # Action done in GitHub. Author is the first word.
                        author = comment.split(' ', 1)[0]

                if 'needs-review' in comment:
                    actions.append((NEEDS_REVIEW, author))
                elif 'needs-changes' in comment:
                    actions.append((DONE_REVIEW, author))
                elif 'changes-approved' in comment:
                    actions.append((DONE_REVIEW, author))
                elif 'Branch landed on master' in comment:
                    actions.append((FIXED, author))
                else:
                    actions.append((JUST_COMMENT, author))

            elif field == 'description':
                actions.append((JUST_COMMENT, author))


        for (action, possibleAuthor) in actions:
            yield (action, ticket, possibleAuthor, time)


def canonicalizeAuthors(actions, aliases):
    """
    Generate a new sequence of actions with author names canonicalized with
    respect to a dictionary of alias definitions.

    @param actions: An action sequence like the one returned by L{getActions}.

    @param aliases: A C{dict} mapping aliases of an author to that author's
        canonical name.
    """
    for (action, ticket, author, time) in actions:
        # Author is lowercased already, by getActions - but maybe that would be
        # better done here.
        yield (action, ticket, aliases.get(author, author), time)



def loadAliases(path):
    """
    Read alias definitions from the given path.

    An alias is defined as one line of text, with the canonical name coming
    first and the alias coming second, separated by a C{","}.
    """
    aliases = {}
    for line in path.getContent().decode('utf8').splitlines():
        canon, alias = line.split(u",", 1)
        aliases[alias.strip()] = canon.strip()
    return aliases


def computeActions(start, end):
    aliases = loadAliases(here.sibling('author-aliases.txt'))
    changes = getChanges(start, end)
    actions = getActions(changes)
    return canonicalizeAuthors(actions, aliases)


def main(start, end, output):
    actions = computeActions(start, end)
    scores = getscores(actions)
    render(output, start, scores)


if __name__ == '__main__':
    import pprint
    start, end = monthRangeAround(Time())
    actions = list(computeActions(start, end))
    pprint.pprint(actions)
    pprint.pprint(getscores(actions))
