#!/usr/bin/env python3
"""  
Name:
    there.py : learn how to change, for the better  
  
Version:
    0.2  
  
Usage:
    there [options]  
  
Options:
  
    -h        Help.  
    -v        Verbose.  
    -r=f      Function to run.   
    -s=n      Set random number seed [default: 1].  
    -k=n      Speed in knots [default: 10].  
  
Examples:
  
    - Installation: `sh INSTALL.md`  
    - Unit tests. 'pytest.py  there.py'  
    - One Unit test. `pytest.py -s -k tion1 there.py`   
    - Continual tests: `rerun 'pytest there.py'`  
    - Documentation: `sh DOC.md`  
    - Add some shell tricks: `sh SH.md`  
  
Notes:
    Simplest to tricky-est, this code divides  
    into `OTHER`,`BINS`,`TABLE`.  
  
    - `OTHER` contains misc  utilities.  
    - `ROW` manages sets of rows.  
    - `BINS` does discretization.  
  
Author:
   Tim Menzies  
   timm@ieee.org  
   http://menzies.us  
  
Copyright:
   (c) 2020 Tim Menzies,   
   MIT license,    
   https://opensource.org/licenses/MIT  
  
"""

import re
import sys
import math
import copy
import bisect
from docopt import docopt
from random import random, seed, choice
from random import shuffle as rshuffle


# ---------------------------------------------
# Misc, lib functions
def opt(d, **types):
  """Coerce dictionaries into simple keys
  whose values are of known `types`."""
  d = {re.sub(r"^[-]+", "", k): v for k, v in d.items()}
  for k, f in types.items():
    d[k] = f(d[k])
  return o(**d)


def same(x): return x
def first(a): return a[0]
def last(a): return a[-1]
def shuffle(a): rshuffle(a); return a


class o:
  """LIB: Class that can pretty print; that
  can `inc`rement and `__add__` their values."""
  def __init__(i, **d):
    i.__dict__.update(**d)

  def __repr__(i):
    "Pretty print. Hide private keys (those starting in `_`)"
    d = i.__dict__
    n = i.__class__.__name__
    return n + "{" + ', '.join(
        [(':%s %s' % (k, d[k])) for k in sorted(d.keys())
            if str(k)[0] != "_"]) + "}"

# ---------------------------------


class Row(o):
  """
  Holds one example from a set of `rows`
  in 'cells' (and, if the row has been descretized,
  in 'bins').
  """
  def __init__(i, rows, cells):
    i._rows = rows
    i.cells = cells
    i.bins = cells[:]
    i.seen = False
    i.dom = 0

  def __getitem__(i, k):
    return i.cells[k]

  def better(i, j):
    c = i._rows.cols
    s1, s2, n = 0, 0, len(c.y) + 0.0001
    for k in c.y:
      x = i.bins[k]
      y = j.bins[k]
      s1 -= math.e**(c.w[k] * (x - y) / n)
      s2 -= math.e**(c.w[k] * (y - x) / n)
    return s1 / n < s2 / n

  def dist(i, j, what="x"):
    d, n = 0, 0
    for c in i._rows.cols[what]:
      a, b = i.cells[c], j.cells[c]
      n += 1
      if a == "?" and b == "?":
        d = 1
      else:
        if a == "?":
          a = 0 if b > 0.5 else 1
        if b == "?":
          b = 0 if a > 0.5 else 1
      d += abs(a - b) ^ 2
    return (d / (n + 0.001))**0.5

  def status(i):
    return [i[y] for y in i._rows.cols.y]


class Rows(o):
  """
  Holds many examples in `rows`.  Also, `cols` stores
  type descriptions for each column (and `cols` is built from the
  names in the first row).
  """
  def __init__(i, src=[]):
    """
    Create from `src`, which could be a list,
    a `.csv` file name, or a string.
    """
    i.all, i._bins = [], {}
    i.cols = o(all={}, w={}, klass=None, x={}, y={}, syms={}, nums={})
    [i.add(row) for row in csv(src)]

  def add(i, row):
    "The first `row` goes to the header. All the rest got to `rows`."
    i.row(row) if i.cols.all else i.header(row)

  ch = o(klass="!", num="$",
         less="<", more=">", skip="?",
         nums="><$", goal="<>!,")

  def header(i, lst):
    """
    Using the magic characters from `Rows.ch`, divide the columns
    into the symbols, the numbers, the x cols, the y cols, the
    klass col. Also, store them all in the `all` list.
    """
    c, ch = i.cols, Rows.ch
    c.klass = -1
    for pos, txt in enumerate(lst):
      c.all[pos] = txt
      (c.nums if txt[0] in ch.nums else c.syms)[pos] = txt
      (c.y if txt[0] in ch.goal else c.x)[pos] = txt
      c.w[pos] = -1 if ch.less in txt else 1
      if ch.klass in txt:
        c.klass = pos

  def row(i, z):
    "add a new row"
    z = z.cells if isinstance(z, Row) else z
    i.all += [Row(i, z)]

  def bins(i, goal=None, cohen=.2):
    """
    Divide numerics into  ranges that best select for `goal`.  If
    `goal=None` then just divide into sqrt(N) bins, that differ
    by more than a small amount (at least `.2*sd`).
    """
    def apply2Numerics(lst, x):
      if x == "?":
        return x
      for pos, bin in enumerate(lst):
        if x < bin.xlo:
          break
        if bin.xlo <= x < bin.xhi:
          break
      return round((pos + 1) / len(lst), 2)
    # ----------------
    for x in i.cols.nums:
      i._bins[x] = bins = Bins.nums(
          i.all, x=x, goal=goal, cohen=cohen, y=i.cols.klass)
    for row in i.all:
      row.bins[x] = apply2Numerics(i._bins[x], row[x])
    for x in i.cols.syms:
      i._bins[x] = Bins.syms(i.all, x=x, goal=goal, y=i.cols.klass)
    return i._bins


class Bin(o):
  """A `bin` is a core data structure in DUO. It
  runs from some `lo` to `hi` value in a column, It is
  associated with some `ys` values. Some bins have higher
  `val`ue than others (i.e. better predict for any
  known goal."""
  def __init__(i, z="__alll__", x=0):
    i.xlo = i.xhi = z
    i.x, i.val = x, 0
    i.ys = {}

  def selects(i, row):
    """Bin`s know the `x` index of the column
    they come from (so `bin`s can be used to select rows
    whose `x` values fall in between `lo` and `hi`."""
    tmp = row[i.x]
    return tmp != "?" and i.xlo <= row[i.x] <= row[i.xhi]

  def score(i, all, e=0.00001):
    "Score a bin by prob*support that it selects for the goal."
    yes = i.ys.get(1, 0) / (all.ys.get(1, 0) + e)
    no = i.ys.get(0, 0) / (all.ys.get(0, 0) + e)
    tmp = yes**2 / (yes + no + e)
    i.val = tmp if tmp > 0.01 else 0
    return i

  def __add__(i, j):
    "Add together the numeric values in `i` and `j`."
    k = Bin(x=i.x)
    k.xlo, k.xhi = i.xlo, j.xhi
    for x, v in i.ys.items():
      k.ys[x] = v
    for x, v in j.ys.items():
      k.ys[x] = v + k.ys.get(x, 0)
    return k

  def inc(i, y, want):
    k = y == want
    i.ys[k] = i.ys.get(k, 0)


class Bins:
  "Bins is a farcade holding code to manage `bin`s."
  def syms(lst, x=0, y=-1, goal=None):
    "Return bins for columns of symbols."
    all = Bin(x=x)
    bins = {}
    for z in lst:
      xx, yy = z[x], z[y]
      if xx != "?":
        if xx not in bins:
          bins[xx] = Bin(xx, x)
        now = bins[xx]
        now.inc(yy, goal)
        all.inc(yy, goal)
    return [Bins.score(one, all) for one in bins.values()]

  def nums(lst, x=0, y=-1, goal=None, cohen=.2,
           enough=.2, trivial=.05):
    """
    Return bins for columns of numbers. Combine two bins if
    they are separated by too small amount or if
    they predict poorly for the goal.
    """
    def split():
      xlo, bins, n = 0, [Bin(0, x)], len(lst)**enough
      while n < 10 and n < len(lst) / 2:
        n *= 1.2
      for xhi, z in enumerate(lst):
        xx, yy = z[x], z[y]
        if xhi - xlo >= n:  # split when big enough
          if len(lst) - xhi >= n:  # split when enough remains after
            if xx != lst[xhi - 1][x]:  # split when values differ
              bins += [Bin(xhi, x)]
              xlo = xhi
        now = bins[-1]
        now.xhi = xhi + 1
        all.xhi = xhi + 1
        now.inc(yy, goal)
        all.inc(yy, goal)
      return [bin.score(all) for bin in bins]

    def merge(bins):
      j, tmp = 0, []
      while j < len(bins):
        a = bins[j]
        if j < len(bins) - 1:
          b = bins[j + 1]
          ab = (a + b).score(all)
          tooLittleDifference = (mid(b) - mid(a)) < cohen
          notBetterForGoal = goal and ab.val >= a.val and ab.val >= b.val
          if tooLittleDifference or notBetterForGoal:
            a = ab
            j += 1
        tmp += [a]
        j += 1
      return bins if len(tmp) == len(bins) else merge(tmp)

    def mid(z): return (n(z.xlo) + n(z.xhi)) / 2
    def per(z=0.5): return lst[int(len(lst) * z)][x]
    def n(z): return lst[min(len(lst) - 1, z)][x]
    def finalize(z): z.xlo, z.xhi = n(z.xlo), n(z.xhi); return z
    # --------------------------------------------------------------
    lst = sorted((z for z in lst if z[x] != "?"), key=lambda z: z[x])
    all = Bin(0, x)
    cohen = cohen * (per(.9) - per(.1)) / 2.54
    return [finalize(bin) for bin in merge(split())]


def smo(tab, n1=10):
  def pairs(lst):
    j = 0
    while j < len(lst) - 1:
      yield lst[j], lst[j + 1]
      j += 2
  lst = shuffle(tab.rows)
  for i, j in pairs(lst[:n1]):
    i.dom += i.better(j)


def csv(src=None, f=sys.stdin):
  """Read from stdio or file or string or list.  Kill whitespace or
  comments. Coerce number strings to numbers."Ignore columns if,
  on line one, the name contains '?'."""
  def items(z):
    for y in z:
      yield y

  def strings(z):
    for y in z.splitlines():
      yield y

  def csv(z):
    with open(z) as fp:
      for y in fp:
        yield y

  def rows(z):
    for y in f(z):
      if isinstance(y, str):
        y = re.sub(r'([\n\t\r ]|#.*)', '', y).strip()
        if y:
          yield y.split(",")
      else:
        yield y

  def floats(a): return a if a == "?" else float(a)

  def nums(z):
    funs, num = None, Rows.ch.nums
    for a in z:
      if funs:
        yield [fun(a1) for fun, a1 in zip(funs, a)]
      else:
        funs = [floats if a1[0] in num else str for a1 in a]
        yield a

  def cols(src, todo=None):
    for a in src:
      todo = todo or [n for n, a1 in enumerate(a) if "?" not in a1]
      yield [a[n] for n in todo]

  if src:
    if isinstance(src, (list, tuple)):
      f = items
    elif isinstance(src, str):
      if src[-3:] == 'csv':
        f = csv
      else:
        f = strings
  for row in nums(cols(rows(src))):
    yield row


def test_struct():
  x = o(b=2, _c=3)
  y = o(b=2, _c=3, f=10)
  z = x + y
  print(z)
  z.inc("b")
  z.inc("k")
  assert(z.b == 5)
  assert(z.k == 1)
  assert(z.f == 10)


def test_csv():
  n = 0
  for row in csv(auto93):
    n += 1
    assert len(row) == 7
  assert n == 399


def test_rows():
  r = Rows(auto93)
  assert len(r.cols.all) == 7
  assert len(r.all) == 398


def test_tab2():
  print(1)
  rows = Rows(diabetes)
  rows.bins('tested_positive')
  for r in rows.all:
    print(r.x, rows.all.col.all[r.x], r.xlo, r.xhi, r.val)


def rest_dom(n=20):
  t = Rows(auto93)
  t.bins(goal=40)
  for r1 in t.rows:
    r1.dom = 0
    for _ in range(n):
      r1.dom += r1.better(choice(t.rows)) / n
  t.rows = sorted(t.rows, key=lambda r: r.dom)
  for row in t.rows[0::n]:
    print(row.status(), round(row.dom, 2))


def rest_pairs():
  for x, y in pairs([1, 2, 3, 4, 5, 6, 7, 8, 9]):
    print(x, y)


def rest_dom():
  t = Rows(auto93)
  t.bins(goal=40)
  for c, b in t._bins.items():
    print(c, t.cols.all[c], len(b))

# -------------------------------------------


auto93 = """
cylinders, $displacement, $horsepower, >weight,>acceleration,$model,?origin,>!mpg
8, 304.0, 193, 4732, 18.5, 70, 1, 10
8, 360, 215, 4615, 14, 70, 1, 10
8, 307, 200, 4376, 15, 70, 1, 10
8, 318, 210, 4382, 13.5, 70, 1, 10
8, 429, 208, 4633, 11, 72, 1, 10
8, 400, 150, 4997, 14, 73, 1, 10
8, 350, 180, 3664, 11, 73, 1, 10
8, 383, 180, 4955, 11.5, 71, 1, 10
8, 350, 160, 4456, 13.5, 72, 1, 10
8, 429, 198, 4952, 11.5, 73, 1, 10
8, 455, 225, 4951, 11, 73, 1, 10
8, 400, 167, 4906, 12.5, 73, 1, 10
8, 350, 180, 4499, 12.5, 73, 1, 10
8, 400, 170, 4746, 12, 71, 1, 10
8, 400, 175, 5140, 12, 71, 1, 10
8, 350, 165, 4274, 12, 72, 1, 10
8, 350, 155, 4502, 13.5, 72, 1, 10
8, 400, 190, 4422, 12.5, 72, 1, 10
8, 307, 130, 4098, 14, 72, 1, 10
8, 302, 140, 4294, 16, 72, 1, 10
8, 350, 175, 4100, 13, 73, 1, 10
8, 350, 145, 3988, 13, 73, 1, 10
8, 400, 150, 4464, 12, 73, 1, 10
8, 351, 158, 4363, 13, 73, 1, 10
8, 440, 215, 4735, 11, 73, 1, 10
8, 360, 175, 3821, 11, 73, 1, 10
8, 360, 170, 4654, 13, 73, 1, 10
8, 350, 150, 4699, 14.5, 74, 1, 10
8, 302, 129, 3169, 12, 75, 1, 10
8, 318, 150, 3940, 13.2, 76, 1, 10
8, 350, 145, 4055, 12, 76, 1, 10
8, 302, 130, 3870, 15, 76, 1, 10
8, 318, 150, 3755, 14, 76, 1, 10
8, 454, 220, 4354, 9, 70, 1, 10
8, 440, 215, 4312, 8.5, 70, 1, 10
8, 455, 225, 4425, 10, 70, 1, 10
8, 340, 160, 3609, 8, 70, 1, 10
8, 455, 225, 3086, 10, 70, 1, 10
8, 350, 165, 4209, 12, 71, 1, 10
8, 400, 175, 4464, 11.5, 71, 1, 10
8, 351, 153, 4154, 13.5, 71, 1, 10
8, 318, 150, 4096, 13, 71, 1, 10
8, 400, 175, 4385, 12, 72, 1, 10
8, 351, 153, 4129, 13, 72, 1, 10
8, 318, 150, 4077, 14, 72, 1, 10
8, 304, 150, 3672, 11.5, 73, 1, 10
8, 302, 137, 4042, 14.5, 73, 1, 10
8, 318, 150, 4237, 14.5, 73, 1, 10
8, 318, 150, 4457, 13.5, 74, 1, 10
8, 302, 140, 4638, 16, 74, 1, 10
8, 304, 150, 4257, 15.5, 74, 1, 10
8, 351, 148, 4657, 13.5, 75, 1, 10
8, 351, 152, 4215, 12.8, 76, 1, 10
8, 350, 165, 3693, 11.5, 70, 1, 20
8, 429, 198, 4341, 10, 70, 1, 20
8, 390, 190, 3850, 8.5, 70, 1, 20
8, 383, 170, 3563, 10, 70, 1, 20
8, 400, 150, 3761, 9.5, 70, 1, 20
8, 318, 150, 4135, 13.5, 72, 1, 20
8, 304, 150, 3892, 12.5, 72, 1, 20
8, 318, 150, 3777, 12.5, 73, 1, 20
8, 350, 145, 4082, 13, 73, 1, 20
8, 318, 150, 3399, 11, 73, 1, 20
6, 250, 100, 3336, 17, 74, 1, 20
6, 250, 72, 3432, 21, 75, 1, 20
6, 250, 72, 3158, 19.5, 75, 1, 20
8, 350, 145, 4440, 14, 75, 1, 20
6, 258, 110, 3730, 19, 75, 1, 20
8, 302, 130, 4295, 14.9, 77, 1, 20
8, 304, 120, 3962, 13.9, 76, 1, 20
8, 318, 145, 4140, 13.7, 77, 1, 20
8, 350, 170, 4165, 11.4, 77, 1, 20
8, 400, 190, 4325, 12.2, 77, 1, 20
8, 351, 142, 4054, 14.3, 79, 1, 20
8, 304, 150, 3433, 12, 70, 1, 20
6, 225, 105, 3439, 15.5, 71, 1, 20
6, 250, 100, 3278, 18, 73, 1, 20
8, 400, 230, 4278, 9.5, 73, 1, 20
6, 250, 100, 3781, 17, 74, 1, 20
6, 258, 110, 3632, 18, 74, 1, 20
8, 302, 140, 4141, 14, 74, 1, 20
8, 400, 170, 4668, 11.5, 75, 1, 20
8, 318, 150, 4498, 14.5, 75, 1, 20
6, 250, 105, 3897, 18.5, 75, 1, 20
8, 318, 150, 4190, 13, 76, 1, 20
8, 400, 180, 4220, 11.1, 77, 1, 20
8, 351, 149, 4335, 14.5, 77, 1, 20
6, 163, 133, 3410, 15.8, 78, 2, 20
6, 168, 120, 3820, 16.7, 76, 2, 20
8, 350, 180, 4380, 12.1, 76, 1, 20
8, 351, 138, 3955, 13.2, 79, 1, 20
8, 350, 155, 4360, 14.9, 79, 1, 20
8, 302, 140, 3449, 10.5, 70, 1, 20
6, 250, 100, 3329, 15.5, 71, 1, 20
8, 304, 150, 3672, 11.5, 72, 1, 20
6, 231, 110, 3907, 21, 75, 1, 20
8, 260, 110, 4060, 19, 77, 1, 20
6, 163, 125, 3140, 13.6, 78, 2, 20
8, 305, 130, 3840, 15.4, 79, 1, 20
8, 305, 140, 4215, 13, 76, 1, 20
6, 258, 95, 3193, 17.8, 76, 1, 20
8, 305, 145, 3880, 12.5, 77, 1, 20
6, 250, 110, 3520, 16.4, 77, 1, 20
8, 318, 140, 4080, 13.7, 78, 1, 20
8, 302, 129, 3725, 13.4, 79, 1, 20
6, 225, 85, 3465, 16.6, 81, 1, 20
6, 231, 165, 3445, 13.4, 78, 1, 20
8, 307, 130, 3504, 12, 70, 1, 20
8, 318, 150, 3436, 11, 70, 1, 20
6, 199, 97, 2774, 15.5, 70, 1, 20
6, 232, 100, 3288, 15.5, 71, 1, 20
6, 258, 110, 2962, 13.5, 71, 1, 20
6, 250, 88, 3139, 14.5, 71, 1, 20
4, 121, 112, 2933, 14.5, 72, 2, 20
6, 225, 105, 3121, 16.5, 73, 1, 20
6, 232, 100, 2945, 16, 73, 1, 20
6, 250, 88, 3021, 16.5, 73, 1, 20
6, 232, 100, 2789, 15, 73, 1, 20
3, 70, 90, 2124, 13.5, 73, 3, 20
6, 225, 105, 3613, 16.5, 74, 1, 20
6, 250, 105, 3459, 16, 75, 1, 20
6, 225, 95, 3785, 19, 75, 1, 20
6, 171, 97, 2984, 14.5, 75, 1, 20
6, 250, 78, 3574, 21, 76, 1, 20
6, 258, 120, 3410, 15.1, 78, 1, 20
8, 302, 139, 3205, 11.2, 78, 1, 20
8, 318, 135, 3830, 15.2, 79, 1, 20
6, 250, 110, 3645, 16.2, 76, 1, 20
6, 250, 98, 3525, 19, 77, 1, 20
8, 360, 150, 3940, 13, 79, 1, 20
6, 225, 110, 3620, 18.7, 78, 1, 20
6, 232, 100, 2634, 13, 71, 1, 20
6, 250, 88, 3302, 15.5, 71, 1, 20
6, 250, 100, 3282, 15, 71, 1, 20
3, 70, 97, 2330, 13.5, 72, 3, 20
4, 122, 85, 2310, 18.5, 73, 1, 20
4, 121, 112, 2868, 15.5, 73, 2, 20
6, 232, 100, 2901, 16, 74, 1, 20
6, 225, 95, 3264, 16, 75, 1, 20
6, 232, 90, 3211, 17, 75, 1, 20
4, 120, 88, 3270, 21.9, 76, 2, 20
6, 156, 108, 2930, 15.5, 76, 3, 20
6, 225, 100, 3630, 17.7, 77, 1, 20
6, 225, 90, 3381, 18.7, 80, 1, 20
6, 231, 105, 3535, 19.2, 78, 1, 20
8, 305, 145, 3425, 13.2, 78, 1, 20
8, 267, 125, 3605, 15, 79, 1, 20
8, 318, 140, 3735, 13.2, 78, 1, 20
6, 232, 90, 3210, 17.2, 78, 1, 20
6, 200, 85, 2990, 18.2, 79, 1, 20
8, 260, 110, 3365, 15.5, 78, 1, 20
4, 140, 90, 2408, 19.5, 72, 1, 20
4, 97, 88, 2279, 19, 73, 3, 20
4, 114, 91, 2582, 14, 73, 2, 20
6, 156, 122, 2807, 13.5, 73, 3, 20
6, 198, 95, 3102, 16.5, 74, 1, 20
8, 262, 110, 3221, 13.5, 75, 1, 20
6, 232, 100, 2914, 16, 75, 1, 20
6, 225, 100, 3651, 17.7, 76, 1, 20
4, 130, 102, 3150, 15.7, 76, 2, 20
8, 302, 139, 3570, 12.8, 78, 1, 20
6, 200, 85, 2965, 15.8, 78, 1, 20
6, 232, 90, 3265, 18.2, 79, 1, 20
6, 200, 88, 3060, 17.1, 81, 1, 20
5, 131, 103, 2830, 15.9, 78, 2, 20
6, 231, 105, 3425, 16.9, 77, 1, 20
6, 200, 95, 3155, 18.2, 78, 1, 20
6, 225, 100, 3430, 17.2, 78, 1, 20
6, 231, 105, 3380, 15.8, 78, 1, 20
6, 225, 110, 3360, 16.6, 79, 1, 20
6, 200, 85, 3070, 16.7, 78, 1, 20
6, 200, 85, 2587, 16, 70, 1, 20
6, 199, 90, 2648, 15, 70, 1, 20
4, 122, 86, 2226, 16.5, 72, 1, 20
4, 120, 87, 2979, 19.5, 72, 2, 20
4, 140, 72, 2401, 19.5, 73, 1, 20
6, 155, 107, 2472, 14, 73, 1, 20
6, 200, ?, 2875, 17, 74, 1, 20
6, 231, 110, 3039, 15, 75, 1, 20
4, 134, 95, 2515, 14.8, 78, 3, 20
4, 121, 110, 2600, 12.8, 77, 2, 20
3, 80, 110, 2720, 13.5, 77, 3, 20
6, 231, 115, 3245, 15.4, 79, 1, 20
4, 121, 115, 2795, 15.7, 78, 2, 20
6, 198, 95, 2833, 15.5, 70, 1, 20
4, 140, 72, 2408, 19, 71, 1, 20
4, 121, 76, 2511, 18, 72, 2, 20
4, 122, 86, 2395, 16, 72, 1, 20
4, 108, 94, 2379, 16.5, 73, 3, 20
4, 121, 98, 2945, 14.5, 75, 2, 20
6, 225, 100, 3233, 15.4, 76, 1, 20
6, 250, 105, 3353, 14.5, 76, 1, 20
6, 146, 97, 2815, 14.5, 77, 3, 20
6, 232, 112, 2835, 14.7, 82, 1, 20
4, 140, 88, 2890, 17.3, 79, 1, 20
6, 231, 110, 3415, 15.8, 81, 1, 20
6, 232, 90, 3085, 17.6, 76, 1, 20
4, 122, 86, 2220, 14, 71, 1, 20
4, 97, 54, 2254, 23.5, 72, 2, 20
4, 120, 97, 2506, 14.5, 72, 3, 20
6, 198, 95, 2904, 16, 73, 1, 20
4, 140, 83, 2639, 17, 75, 1, 20
4, 140, 78, 2592, 18.5, 75, 1, 20
4, 115, 95, 2694, 15, 75, 2, 20
4, 120, 88, 2957, 17, 75, 2, 20
8, 350, 125, 3900, 17.4, 79, 1, 20
4, 151, ?, 3035, 20.5, 82, 1, 20
4, 156, 105, 2745, 16.7, 78, 1, 20
6, 173, 110, 2725, 12.6, 81, 1, 20
4, 140, ?, 2905, 14.3, 80, 1, 20
3, 70, 100, 2420, 12.5, 80, 3, 20
4, 151, 85, 2855, 17.6, 78, 1, 20
4, 119, 97, 2405, 14.9, 78, 3, 20
8, 260, 90, 3420, 22.2, 79, 1, 20
4, 113, 95, 2372, 15, 70, 3, 20
4, 107, 90, 2430, 14.5, 70, 2, 20
4, 113, 95, 2278, 15.5, 72, 3, 20
4, 116, 75, 2158, 15.5, 73, 2, 20
4, 121, 110, 2660, 14, 73, 2, 20
4, 90, 75, 2108, 15.5, 74, 2, 20
4, 120, 97, 2489, 15, 74, 3, 20
4, 134, 96, 2702, 13.5, 75, 3, 20
4, 119, 97, 2545, 17, 75, 3, 20
6, 200, 81, 3012, 17.6, 76, 1, 20
4, 140, 92, 2865, 16.4, 82, 1, 20
6, 146, 120, 2930, 13.8, 81, 3, 20
4, 151, 90, 3003, 20.1, 80, 1, 20
4, 98, 60, 2164, 22.1, 76, 1, 20
4, 151, 88, 2740, 16, 77, 1, 20
4, 110, 87, 2672, 17.5, 70, 2, 30
4, 104, 95, 2375, 17.5, 70, 2, 30
4, 113, 95, 2228, 14, 71, 3, 30
4, 98, ?, 2046, 19, 71, 1, 30
4, 97.5, 80, 2126, 17, 72, 1, 30
4, 140, 75, 2542, 17, 74, 1, 30
4, 90, 71, 2223, 16.5, 75, 2, 30
4, 121, 115, 2671, 13.5, 75, 2, 30
4, 116, 81, 2220, 16.9, 76, 2, 30
4, 140, 92, 2572, 14.9, 76, 1, 30
6, 181, 110, 2945, 16.4, 82, 1, 30
4, 140, 88, 2720, 15.4, 78, 1, 30
5, 183, 77, 3530, 20.1, 79, 2, 30
6, 168, 116, 2900, 12.6, 81, 3, 30
4, 122, 96, 2300, 15.5, 77, 1, 30
4, 140, 89, 2755, 15.8, 77, 1, 30
4, 156, 92, 2620, 14.4, 81, 1, 30
4, 97, 46, 1835, 20.5, 70, 2, 30
4, 121, 113, 2234, 12.5, 70, 2, 30
4, 91, 70, 1955, 20.5, 71, 1, 30
4, 96, 69, 2189, 18, 72, 2, 30
4, 97, 46, 1950, 21, 73, 2, 30
4, 98, 90, 2265, 15.5, 73, 2, 30
4, 122, 80, 2451, 16.5, 74, 1, 30
4, 79, 67, 1963, 15.5, 74, 2, 30
4, 97, 78, 2300, 14.5, 74, 2, 30
4, 116, 75, 2246, 14, 74, 2, 30
4, 108, 93, 2391, 15.5, 74, 3, 30
4, 98, 79, 2255, 17.7, 76, 1, 30
4, 97, 75, 2265, 18.2, 77, 3, 30
4, 156, 92, 2585, 14.5, 82, 1, 30
4, 140, 88, 2870, 18.1, 80, 1, 30
4, 140, 72, 2565, 13.6, 76, 1, 30
4, 151, 84, 2635, 16.4, 81, 1, 30
8, 350, 105, 3725, 19, 81, 1, 30
6, 173, 115, 2700, 12.9, 79, 1, 30
4, 97, 88, 2130, 14.5, 70, 3, 30
4, 97, 88, 2130, 14.5, 71, 3, 30
4, 97, 60, 1834, 19, 71, 2, 30
4, 97, 88, 2100, 16.5, 72, 3, 30
4, 101, 83, 2202, 15.3, 76, 2, 30
4, 112, 88, 2640, 18.6, 82, 1, 30
4, 151, 90, 2735, 18, 82, 1, 30
4, 151, 90, 2950, 17.3, 82, 1, 30
4, 140, 86, 2790, 15.6, 82, 1, 30
4, 119, 97, 2300, 14.7, 78, 3, 30
4, 141, 71, 3190, 24.8, 79, 2, 30
4, 135, 84, 2490, 15.7, 81, 1, 30
4, 121, 80, 2670, 15, 79, 1, 30
4, 134, 95, 2560, 14.2, 78, 3, 30
4, 156, 105, 2800, 14.4, 80, 1, 30
4, 140, 90, 2264, 15.5, 71, 1, 30
4, 116, 90, 2123, 14, 71, 2, 30
4, 97, 92, 2288, 17, 72, 3, 30
4, 98, 80, 2164, 15, 72, 1, 30
4, 90, 75, 2125, 14.5, 74, 1, 30
4, 107, 86, 2464, 15.5, 76, 2, 30
4, 97, 75, 2155, 16.4, 76, 3, 30
4, 151, 90, 2678, 16.5, 80, 1, 30
4, 112, 88, 2605, 19.6, 82, 1, 30
4, 120, 79, 2625, 18.6, 82, 1, 30
4, 141, 80, 3230, 20.4, 81, 2, 30
4, 151, 90, 2670, 16, 79, 1, 30
6, 173, 115, 2595, 11.3, 79, 1, 30
4, 68, 49, 1867, 19.5, 73, 2, 30
4, 98, 83, 2219, 16.5, 74, 2, 30
4, 97, 75, 2171, 16, 75, 3, 30
4, 90, 70, 1937, 14, 75, 2, 30
4, 85, 52, 2035, 22.2, 76, 1, 30
4, 90, 70, 1937, 14.2, 76, 2, 30
4, 97, 78, 1940, 14.5, 77, 2, 30
4, 135, 84, 2525, 16, 82, 1, 30
4, 97, 71, 1825, 12.2, 76, 2, 30
4, 98, 68, 2135, 16.6, 78, 3, 30
4, 134, 90, 2711, 15.5, 80, 3, 30
4, 89, 62, 1845, 15.3, 80, 2, 30
4, 98, 65, 2380, 20.7, 81, 1, 30
4, 79, 70, 2074, 19.5, 71, 2, 30
4, 88, 76, 2065, 14.5, 71, 2, 30
4, 111, 80, 2155, 14.8, 77, 1, 30
4, 97, 67, 1985, 16.4, 77, 3, 30
4, 98, 68, 2155, 16.5, 78, 1, 30
4, 146, 67, 3250, 21.8, 80, 2, 30
4, 135, 84, 2385, 12.9, 81, 1, 30
4, 98, 63, 2051, 17, 77, 1, 30
4, 97, 78, 2190, 14.1, 77, 2, 30
6, 145, 76, 3160, 19.6, 81, 2, 30
4, 105, 75, 2230, 14.5, 78, 1, 30
4, 71, 65, 1773, 19, 71, 3, 30
4, 79, 67, 1950, 19, 74, 3, 30
4, 76, 52, 1649, 16.5, 74, 3, 30
4, 79, 67, 2000, 16, 74, 2, 30
4, 112, 85, 2575, 16.2, 82, 1, 30
4, 91, 68, 1970, 17.6, 82, 3, 30
4, 119, 82, 2720, 19.4, 82, 1, 30
4, 120, 75, 2542, 17.5, 80, 3, 30
4, 98, 68, 2045, 18.5, 77, 3, 30
4, 89, 71, 1990, 14.9, 78, 2, 30
4, 120, 74, 2635, 18.3, 81, 3, 30
4, 85, 65, 2020, 19.2, 79, 3, 30
4, 89, 71, 1925, 14, 79, 2, 30
4, 71, 65, 1836, 21, 74, 3, 30
4, 83, 61, 2003, 19, 74, 3, 30
4, 85, 70, 1990, 17, 76, 3, 30
4, 91, 67, 1965, 15.7, 82, 3, 30
4, 144, 96, 2665, 13.9, 82, 3, 30
4, 135, 84, 2295, 11.6, 82, 1, 30
4, 98, 70, 2120, 15.5, 80, 1, 30
4, 108, 75, 2265, 15.2, 80, 3, 30
4, 97, 67, 2065, 17.8, 81, 3, 30
4, 107, 72, 2290, 17, 80, 3, 30
4, 108, 75, 2350, 16.8, 81, 3, 30
6, 168, 132, 2910, 11.4, 80, 3, 30
4, 78, 52, 1985, 19.4, 78, 3, 30
4, 119, 100, 2615, 14.8, 81, 3, 30
4, 91, 53, 1795, 17.5, 75, 3, 30
4, 91, 53, 1795, 17.4, 76, 3, 30
4, 105, 74, 2190, 14.2, 81, 2, 30
4, 85, 70, 1945, 16.8, 77, 3, 30
4, 98, 83, 2075, 15.9, 77, 1, 30
4, 151, 90, 2556, 13.2, 79, 1, 30
4, 107, 75, 2210, 14.4, 81, 3, 30
4, 97, 67, 2145, 18, 80, 3, 30
4, 112, 88, 2395, 18, 82, 1, 30
4, 108, 70, 2245, 16.9, 82, 3, 30
4, 86, 65, 1975, 15.2, 79, 3, 30
4, 91, 68, 1985, 16, 81, 3, 30
4, 105, 70, 2200, 13.2, 79, 1, 30
4, 97, 78, 2188, 15.8, 80, 2, 30
4, 98, 65, 2045, 16.2, 81, 1, 30
4, 105, 70, 2150, 14.9, 79, 1, 30
4, 100, ?, 2320, 15.8, 81, 2, 30
4, 105, 63, 2215, 14.9, 81, 1, 30
4, 72, 69, 1613, 18, 71, 3, 40
4, 122, 88, 2500, 15.1, 80, 2, 40
4, 81, 60, 1760, 16.1, 81, 3, 40
4, 98, 80, 1915, 14.4, 79, 1, 40
4, 79, 58, 1825, 18.6, 77, 2, 40
4, 105, 74, 1980, 15.3, 82, 2, 40
4, 98, 70, 2125, 17.3, 82, 1, 40
4, 120, 88, 2160, 14.5, 82, 3, 40
4, 107, 75, 2205, 14.5, 82, 3, 40
4, 135, 84, 2370, 13, 82, 1, 40
4, 98, 66, 1800, 14.4, 78, 1, 40
4, 91, 60, 1800, 16.4, 78, 3, 40
5, 121, 67, 2950, 19.9, 80, 2, 40
4, 119, 92, 2434, 15, 80, 3, 40
4, 85, 65, 1975, 19.4, 81, 3, 40
4, 91, 68, 2025, 18.2, 82, 3, 40
4, 86, 65, 2019, 16.4, 80, 3, 40
4, 91, 69, 2130, 14.7, 79, 2, 40
4, 89, 62, 2050, 17.3, 81, 3, 40
4, 105, 63, 2125, 14.7, 82, 1, 40
4, 91, 67, 1965, 15, 82, 3, 40
4, 91, 67, 1995, 16.2, 82, 3, 40
6, 262, 85, 3015, 17, 82, 1, 40
4, 89, 60, 1968, 18.8, 80, 3, 40
4, 86, 64, 1875, 16.4, 81, 1, 40
4, 79, 58, 1755, 16.9, 81, 3, 40
4, 85, 70, 2070, 18.6, 78, 3, 40
4, 85, 65, 2110, 19.2, 80, 3, 40
4, 85, ?, 1835, 17.3, 80, 2, 40
4, 98, 76, 2144, 14.7, 80, 2, 40
4, 90, 48, 1985, 21.5, 78, 2, 40
4, 90, 48, 2335, 23.7, 80, 2, 40
4, 97, 52, 2130, 24.6, 82, 2, 40
4, 90, 48, 2085, 21.7, 80, 2, 40
4, 91, 67, 1850, 13.8, 80, 3, 40
4, 86, 65, 2110, 17.9, 80, 3, 50
"""

diabetes = """
$preg, $plas, $pres, $skin, $insu, $mass, $pedi, $age, "class
6, 148, 72, 35, 0, 33.6, 0.627, 50, tested_positive
1, 85, 66, 29, 0, 26.6, 0.351, 31, tested_negative
8, 183, 64, 0, 0, 23.3, 0.672, 32, tested_positive
1, 89, 66, 23, 94, 28.1, 0.167, 21, tested_negative
0, 137, 40, 35, 168, 43.1, 2.288, 33, tested_positive
5, 116, 74, 0, 0, 25.6, 0.201, 30, tested_negative
3, 78, 50, 32, 88, 31, 0.248, 26, tested_positive
10, 115, 0, 0, 0, 35.3, 0.134, 29, tested_negative
2, 197, 70, 45, 543, 30.5, 0.158, 53, tested_positive
8, 125, 96, 0, 0, 0, 0.232, 54, tested_positive
4, 110, 92, 0, 0, 37.6, 0.191, 30, tested_negative
10, 168, 74, 0, 0, 38, 0.537, 34, tested_positive
10, 139, 80, 0, 0, 27.1, 1.441, 57, tested_negative
1, 189, 60, 23, 846, 30.1, 0.398, 59, tested_positive
5, 166, 72, 19, 175, 25.8, 0.587, 51, tested_positive
7, 100, 0, 0, 0, 30, 0.484, 32, tested_positive
0, 118, 84, 47, 230, 45.8, 0.551, 31, tested_positive
7, 107, 74, 0, 0, 29.6, 0.254, 31, tested_positive
1, 103, 30, 38, 83, 43.3, 0.183, 33, tested_negative
1, 115, 70, 30, 96, 34.6, 0.529, 32, tested_positive
3, 126, 88, 41, 235, 39.3, 0.704, 27, tested_negative
8, 99, 84, 0, 0, 35.4, 0.388, 50, tested_negative
7, 196, 90, 0, 0, 39.8, 0.451, 41, tested_positive
9, 119, 80, 35, 0, 29, 0.263, 29, tested_positive
11, 143, 94, 33, 146, 36.6, 0.254, 51, tested_positive
10, 125, 70, 26, 115, 31.1, 0.205, 41, tested_positive
7, 147, 76, 0, 0, 39.4, 0.257, 43, tested_positive
1, 97, 66, 15, 140, 23.2, 0.487, 22, tested_negative
13, 145, 82, 19, 110, 22.2, 0.245, 57, tested_negative
5, 117, 92, 0, 0, 34.1, 0.337, 38, tested_negative
5, 109, 75, 26, 0, 36, 0.546, 60, tested_negative
3, 158, 76, 36, 245, 31.6, 0.851, 28, tested_positive
3, 88, 58, 11, 54, 24.8, 0.267, 22, tested_negative
6, 92, 92, 0, 0, 19.9, 0.188, 28, tested_negative
10, 122, 78, 31, 0, 27.6, 0.512, 45, tested_negative
4, 103, 60, 33, 192, 24, 0.966, 33, tested_negative
11, 138, 76, 0, 0, 33.2, 0.42, 35, tested_negative
9, 102, 76, 37, 0, 32.9, 0.665, 46, tested_positive
2, 90, 68, 42, 0, 38.2, 0.503, 27, tested_positive
4, 111, 72, 47, 207, 37.1, 1.39, 56, tested_positive
3, 180, 64, 25, 70, 34, 0.271, 26, tested_negative
7, 133, 84, 0, 0, 40.2, 0.696, 37, tested_negative
7, 106, 92, 18, 0, 22.7, 0.235, 48, tested_negative
9, 171, 110, 24, 240, 45.4, 0.721, 54, tested_positive
7, 159, 64, 0, 0, 27.4, 0.294, 40, tested_negative
0, 180, 66, 39, 0, 42, 1.893, 25, tested_positive
1, 146, 56, 0, 0, 29.7, 0.564, 29, tested_negative
2, 71, 70, 27, 0, 28, 0.586, 22, tested_negative
7, 103, 66, 32, 0, 39.1, 0.344, 31, tested_positive
7, 105, 0, 0, 0, 0, 0.305, 24, tested_negative
1, 103, 80, 11, 82, 19.4, 0.491, 22, tested_negative
1, 101, 50, 15, 36, 24.2, 0.526, 26, tested_negative
5, 88, 66, 21, 23, 24.4, 0.342, 30, tested_negative
8, 176, 90, 34, 300, 33.7, 0.467, 58, tested_positive
7, 150, 66, 42, 342, 34.7, 0.718, 42, tested_negative
1, 73, 50, 10, 0, 23, 0.248, 21, tested_negative
7, 187, 68, 39, 304, 37.7, 0.254, 41, tested_positive
0, 100, 88, 60, 110, 46.8, 0.962, 31, tested_negative
0, 146, 82, 0, 0, 40.5, 1.781, 44, tested_negative
0, 105, 64, 41, 142, 41.5, 0.173, 22, tested_negative
2, 84, 0, 0, 0, 0, 0.304, 21, tested_negative
8, 133, 72, 0, 0, 32.9, 0.27, 39, tested_positive
5, 44, 62, 0, 0, 25, 0.587, 36, tested_negative
2, 141, 58, 34, 128, 25.4, 0.699, 24, tested_negative
7, 114, 66, 0, 0, 32.8, 0.258, 42, tested_positive
5, 99, 74, 27, 0, 29, 0.203, 32, tested_negative
0, 109, 88, 30, 0, 32.5, 0.855, 38, tested_positive
2, 109, 92, 0, 0, 42.7, 0.845, 54, tested_negative
1, 95, 66, 13, 38, 19.6, 0.334, 25, tested_negative
4, 146, 85, 27, 100, 28.9, 0.189, 27, tested_negative
2, 100, 66, 20, 90, 32.9, 0.867, 28, tested_positive
5, 139, 64, 35, 140, 28.6, 0.411, 26, tested_negative
13, 126, 90, 0, 0, 43.4, 0.583, 42, tested_positive
4, 129, 86, 20, 270, 35.1, 0.231, 23, tested_negative
1, 79, 75, 30, 0, 32, 0.396, 22, tested_negative
1, 0, 48, 20, 0, 24.7, 0.14, 22, tested_negative
7, 62, 78, 0, 0, 32.6, 0.391, 41, tested_negative
5, 95, 72, 33, 0, 37.7, 0.37, 27, tested_negative
0, 131, 0, 0, 0, 43.2, 0.27, 26, tested_positive
2, 112, 66, 22, 0, 25, 0.307, 24, tested_negative
3, 113, 44, 13, 0, 22.4, 0.14, 22, tested_negative
2, 74, 0, 0, 0, 0, 0.102, 22, tested_negative
7, 83, 78, 26, 71, 29.3, 0.767, 36, tested_negative
0, 101, 65, 28, 0, 24.6, 0.237, 22, tested_negative
5, 137, 108, 0, 0, 48.8, 0.227, 37, tested_positive
2, 110, 74, 29, 125, 32.4, 0.698, 27, tested_negative
13, 106, 72, 54, 0, 36.6, 0.178, 45, tested_negative
2, 100, 68, 25, 71, 38.5, 0.324, 26, tested_negative
15, 136, 70, 32, 110, 37.1, 0.153, 43, tested_positive
1, 107, 68, 19, 0, 26.5, 0.165, 24, tested_negative
1, 80, 55, 0, 0, 19.1, 0.258, 21, tested_negative
4, 123, 80, 15, 176, 32, 0.443, 34, tested_negative
7, 81, 78, 40, 48, 46.7, 0.261, 42, tested_negative
4, 134, 72, 0, 0, 23.8, 0.277, 60, tested_positive
2, 142, 82, 18, 64, 24.7, 0.761, 21, tested_negative
6, 144, 72, 27, 228, 33.9, 0.255, 40, tested_negative
2, 92, 62, 28, 0, 31.6, 0.13, 24, tested_negative
1, 71, 48, 18, 76, 20.4, 0.323, 22, tested_negative
6, 93, 50, 30, 64, 28.7, 0.356, 23, tested_negative
1, 122, 90, 51, 220, 49.7, 0.325, 31, tested_positive
1, 163, 72, 0, 0, 39, 1.222, 33, tested_positive
1, 151, 60, 0, 0, 26.1, 0.179, 22, tested_negative
0, 125, 96, 0, 0, 22.5, 0.262, 21, tested_negative
1, 81, 72, 18, 40, 26.6, 0.283, 24, tested_negative
2, 85, 65, 0, 0, 39.6, 0.93, 27, tested_negative
1, 126, 56, 29, 152, 28.7, 0.801, 21, tested_negative
1, 96, 122, 0, 0, 22.4, 0.207, 27, tested_negative
4, 144, 58, 28, 140, 29.5, 0.287, 37, tested_negative
3, 83, 58, 31, 18, 34.3, 0.336, 25, tested_negative
0, 95, 85, 25, 36, 37.4, 0.247, 24, tested_positive
3, 171, 72, 33, 135, 33.3, 0.199, 24, tested_positive
8, 155, 62, 26, 495, 34, 0.543, 46, tested_positive
1, 89, 76, 34, 37, 31.2, 0.192, 23, tested_negative
4, 76, 62, 0, 0, 34, 0.391, 25, tested_negative
7, 160, 54, 32, 175, 30.5, 0.588, 39, tested_positive
4, 146, 92, 0, 0, 31.2, 0.539, 61, tested_positive
5, 124, 74, 0, 0, 34, 0.22, 38, tested_positive
5, 78, 48, 0, 0, 33.7, 0.654, 25, tested_negative
4, 97, 60, 23, 0, 28.2, 0.443, 22, tested_negative
4, 99, 76, 15, 51, 23.2, 0.223, 21, tested_negative
0, 162, 76, 56, 100, 53.2, 0.759, 25, tested_positive
6, 111, 64, 39, 0, 34.2, 0.26, 24, tested_negative
2, 107, 74, 30, 100, 33.6, 0.404, 23, tested_negative
5, 132, 80, 0, 0, 26.8, 0.186, 69, tested_negative
0, 113, 76, 0, 0, 33.3, 0.278, 23, tested_positive
1, 88, 30, 42, 99, 55, 0.496, 26, tested_positive
3, 120, 70, 30, 135, 42.9, 0.452, 30, tested_negative
1, 118, 58, 36, 94, 33.3, 0.261, 23, tested_negative
1, 117, 88, 24, 145, 34.5, 0.403, 40, tested_positive
0, 105, 84, 0, 0, 27.9, 0.741, 62, tested_positive
4, 173, 70, 14, 168, 29.7, 0.361, 33, tested_positive
9, 122, 56, 0, 0, 33.3, 1.114, 33, tested_positive
3, 170, 64, 37, 225, 34.5, 0.356, 30, tested_positive
8, 84, 74, 31, 0, 38.3, 0.457, 39, tested_negative
2, 96, 68, 13, 49, 21.1, 0.647, 26, tested_negative
2, 125, 60, 20, 140, 33.8, 0.088, 31, tested_negative
0, 100, 70, 26, 50, 30.8, 0.597, 21, tested_negative
0, 93, 60, 25, 92, 28.7, 0.532, 22, tested_negative
0, 129, 80, 0, 0, 31.2, 0.703, 29, tested_negative
5, 105, 72, 29, 325, 36.9, 0.159, 28, tested_negative
3, 128, 78, 0, 0, 21.1, 0.268, 55, tested_negative
5, 106, 82, 30, 0, 39.5, 0.286, 38, tested_negative
2, 108, 52, 26, 63, 32.5, 0.318, 22, tested_negative
10, 108, 66, 0, 0, 32.4, 0.272, 42, tested_positive
4, 154, 62, 31, 284, 32.8, 0.237, 23, tested_negative
0, 102, 75, 23, 0, 0, 0.572, 21, tested_negative
9, 57, 80, 37, 0, 32.8, 0.096, 41, tested_negative
2, 106, 64, 35, 119, 30.5, 1.4, 34, tested_negative
5, 147, 78, 0, 0, 33.7, 0.218, 65, tested_negative
2, 90, 70, 17, 0, 27.3, 0.085, 22, tested_negative
1, 136, 74, 50, 204, 37.4, 0.399, 24, tested_negative
4, 114, 65, 0, 0, 21.9, 0.432, 37, tested_negative
9, 156, 86, 28, 155, 34.3, 1.189, 42, tested_positive
1, 153, 82, 42, 485, 40.6, 0.687, 23, tested_negative
8, 188, 78, 0, 0, 47.9, 0.137, 43, tested_positive
7, 152, 88, 44, 0, 50, 0.337, 36, tested_positive
2, 99, 52, 15, 94, 24.6, 0.637, 21, tested_negative
1, 109, 56, 21, 135, 25.2, 0.833, 23, tested_negative
2, 88, 74, 19, 53, 29, 0.229, 22, tested_negative
17, 163, 72, 41, 114, 40.9, 0.817, 47, tested_positive
4, 151, 90, 38, 0, 29.7, 0.294, 36, tested_negative
7, 102, 74, 40, 105, 37.2, 0.204, 45, tested_negative
0, 114, 80, 34, 285, 44.2, 0.167, 27, tested_negative
2, 100, 64, 23, 0, 29.7, 0.368, 21, tested_negative
0, 131, 88, 0, 0, 31.6, 0.743, 32, tested_positive
6, 104, 74, 18, 156, 29.9, 0.722, 41, tested_positive
3, 148, 66, 25, 0, 32.5, 0.256, 22, tested_negative
4, 120, 68, 0, 0, 29.6, 0.709, 34, tested_negative
4, 110, 66, 0, 0, 31.9, 0.471, 29, tested_negative
3, 111, 90, 12, 78, 28.4, 0.495, 29, tested_negative
6, 102, 82, 0, 0, 30.8, 0.18, 36, tested_positive
6, 134, 70, 23, 130, 35.4, 0.542, 29, tested_positive
2, 87, 0, 23, 0, 28.9, 0.773, 25, tested_negative
1, 79, 60, 42, 48, 43.5, 0.678, 23, tested_negative
2, 75, 64, 24, 55, 29.7, 0.37, 33, tested_negative
8, 179, 72, 42, 130, 32.7, 0.719, 36, tested_positive
6, 85, 78, 0, 0, 31.2, 0.382, 42, tested_negative
0, 129, 110, 46, 130, 67.1, 0.319, 26, tested_positive
5, 143, 78, 0, 0, 45, 0.19, 47, tested_negative
5, 130, 82, 0, 0, 39.1, 0.956, 37, tested_positive
6, 87, 80, 0, 0, 23.2, 0.084, 32, tested_negative
0, 119, 64, 18, 92, 34.9, 0.725, 23, tested_negative
1, 0, 74, 20, 23, 27.7, 0.299, 21, tested_negative
5, 73, 60, 0, 0, 26.8, 0.268, 27, tested_negative
4, 141, 74, 0, 0, 27.6, 0.244, 40, tested_negative
7, 194, 68, 28, 0, 35.9, 0.745, 41, tested_positive
8, 181, 68, 36, 495, 30.1, 0.615, 60, tested_positive
1, 128, 98, 41, 58, 32, 1.321, 33, tested_positive
8, 109, 76, 39, 114, 27.9, 0.64, 31, tested_positive
5, 139, 80, 35, 160, 31.6, 0.361, 25, tested_positive
3, 111, 62, 0, 0, 22.6, 0.142, 21, tested_negative
9, 123, 70, 44, 94, 33.1, 0.374, 40, tested_negative
7, 159, 66, 0, 0, 30.4, 0.383, 36, tested_positive
11, 135, 0, 0, 0, 52.3, 0.578, 40, tested_positive
8, 85, 55, 20, 0, 24.4, 0.136, 42, tested_negative
5, 158, 84, 41, 210, 39.4, 0.395, 29, tested_positive
1, 105, 58, 0, 0, 24.3, 0.187, 21, tested_negative
3, 107, 62, 13, 48, 22.9, 0.678, 23, tested_positive
4, 109, 64, 44, 99, 34.8, 0.905, 26, tested_positive
4, 148, 60, 27, 318, 30.9, 0.15, 29, tested_positive
0, 113, 80, 16, 0, 31, 0.874, 21, tested_negative
1, 138, 82, 0, 0, 40.1, 0.236, 28, tested_negative
0, 108, 68, 20, 0, 27.3, 0.787, 32, tested_negative
2, 99, 70, 16, 44, 20.4, 0.235, 27, tested_negative
6, 103, 72, 32, 190, 37.7, 0.324, 55, tested_negative
5, 111, 72, 28, 0, 23.9, 0.407, 27, tested_negative
8, 196, 76, 29, 280, 37.5, 0.605, 57, tested_positive
5, 162, 104, 0, 0, 37.7, 0.151, 52, tested_positive
1, 96, 64, 27, 87, 33.2, 0.289, 21, tested_negative
7, 184, 84, 33, 0, 35.5, 0.355, 41, tested_positive
2, 81, 60, 22, 0, 27.7, 0.29, 25, tested_negative
0, 147, 85, 54, 0, 42.8, 0.375, 24, tested_negative
7, 179, 95, 31, 0, 34.2, 0.164, 60, tested_negative
0, 140, 65, 26, 130, 42.6, 0.431, 24, tested_positive
9, 112, 82, 32, 175, 34.2, 0.26, 36, tested_positive
12, 151, 70, 40, 271, 41.8, 0.742, 38, tested_positive
5, 109, 62, 41, 129, 35.8, 0.514, 25, tested_positive
6, 125, 68, 30, 120, 30, 0.464, 32, tested_negative
5, 85, 74, 22, 0, 29, 1.224, 32, tested_positive
5, 112, 66, 0, 0, 37.8, 0.261, 41, tested_positive
0, 177, 60, 29, 478, 34.6, 1.072, 21, tested_positive
2, 158, 90, 0, 0, 31.6, 0.805, 66, tested_positive
7, 119, 0, 0, 0, 25.2, 0.209, 37, tested_negative
7, 142, 60, 33, 190, 28.8, 0.687, 61, tested_negative
1, 100, 66, 15, 56, 23.6, 0.666, 26, tested_negative
1, 87, 78, 27, 32, 34.6, 0.101, 22, tested_negative
0, 101, 76, 0, 0, 35.7, 0.198, 26, tested_negative
3, 162, 52, 38, 0, 37.2, 0.652, 24, tested_positive
4, 197, 70, 39, 744, 36.7, 2.329, 31, tested_negative
0, 117, 80, 31, 53, 45.2, 0.089, 24, tested_negative
4, 142, 86, 0, 0, 44, 0.645, 22, tested_positive
6, 134, 80, 37, 370, 46.2, 0.238, 46, tested_positive
1, 79, 80, 25, 37, 25.4, 0.583, 22, tested_negative
4, 122, 68, 0, 0, 35, 0.394, 29, tested_negative
3, 74, 68, 28, 45, 29.7, 0.293, 23, tested_negative
4, 171, 72, 0, 0, 43.6, 0.479, 26, tested_positive
7, 181, 84, 21, 192, 35.9, 0.586, 51, tested_positive
0, 179, 90, 27, 0, 44.1, 0.686, 23, tested_positive
9, 164, 84, 21, 0, 30.8, 0.831, 32, tested_positive
0, 104, 76, 0, 0, 18.4, 0.582, 27, tested_negative
1, 91, 64, 24, 0, 29.2, 0.192, 21, tested_negative
4, 91, 70, 32, 88, 33.1, 0.446, 22, tested_negative
3, 139, 54, 0, 0, 25.6, 0.402, 22, tested_positive
6, 119, 50, 22, 176, 27.1, 1.318, 33, tested_positive
2, 146, 76, 35, 194, 38.2, 0.329, 29, tested_negative
9, 184, 85, 15, 0, 30, 1.213, 49, tested_positive
10, 122, 68, 0, 0, 31.2, 0.258, 41, tested_negative
0, 165, 90, 33, 680, 52.3, 0.427, 23, tested_negative
9, 124, 70, 33, 402, 35.4, 0.282, 34, tested_negative
1, 111, 86, 19, 0, 30.1, 0.143, 23, tested_negative
9, 106, 52, 0, 0, 31.2, 0.38, 42, tested_negative
2, 129, 84, 0, 0, 28, 0.284, 27, tested_negative
2, 90, 80, 14, 55, 24.4, 0.249, 24, tested_negative
0, 86, 68, 32, 0, 35.8, 0.238, 25, tested_negative
12, 92, 62, 7, 258, 27.6, 0.926, 44, tested_positive
1, 113, 64, 35, 0, 33.6, 0.543, 21, tested_positive
3, 111, 56, 39, 0, 30.1, 0.557, 30, tested_negative
2, 114, 68, 22, 0, 28.7, 0.092, 25, tested_negative
1, 193, 50, 16, 375, 25.9, 0.655, 24, tested_negative
11, 155, 76, 28, 150, 33.3, 1.353, 51, tested_positive
3, 191, 68, 15, 130, 30.9, 0.299, 34, tested_negative
3, 141, 0, 0, 0, 30, 0.761, 27, tested_positive
4, 95, 70, 32, 0, 32.1, 0.612, 24, tested_negative
3, 142, 80, 15, 0, 32.4, 0.2, 63, tested_negative
4, 123, 62, 0, 0, 32, 0.226, 35, tested_positive
5, 96, 74, 18, 67, 33.6, 0.997, 43, tested_negative
0, 138, 0, 0, 0, 36.3, 0.933, 25, tested_positive
2, 128, 64, 42, 0, 40, 1.101, 24, tested_negative
0, 102, 52, 0, 0, 25.1, 0.078, 21, tested_negative
2, 146, 0, 0, 0, 27.5, 0.24, 28, tested_positive
10, 101, 86, 37, 0, 45.6, 1.136, 38, tested_positive
2, 108, 62, 32, 56, 25.2, 0.128, 21, tested_negative
3, 122, 78, 0, 0, 23, 0.254, 40, tested_negative
1, 71, 78, 50, 45, 33.2, 0.422, 21, tested_negative
13, 106, 70, 0, 0, 34.2, 0.251, 52, tested_negative
2, 100, 70, 52, 57, 40.5, 0.677, 25, tested_negative
7, 106, 60, 24, 0, 26.5, 0.296, 29, tested_positive
0, 104, 64, 23, 116, 27.8, 0.454, 23, tested_negative
5, 114, 74, 0, 0, 24.9, 0.744, 57, tested_negative
2, 108, 62, 10, 278, 25.3, 0.881, 22, tested_negative
0, 146, 70, 0, 0, 37.9, 0.334, 28, tested_positive
10, 129, 76, 28, 122, 35.9, 0.28, 39, tested_negative
7, 133, 88, 15, 155, 32.4, 0.262, 37, tested_negative
7, 161, 86, 0, 0, 30.4, 0.165, 47, tested_positive
2, 108, 80, 0, 0, 27, 0.259, 52, tested_positive
7, 136, 74, 26, 135, 26, 0.647, 51, tested_negative
5, 155, 84, 44, 545, 38.7, 0.619, 34, tested_negative
1, 119, 86, 39, 220, 45.6, 0.808, 29, tested_positive
4, 96, 56, 17, 49, 20.8, 0.34, 26, tested_negative
5, 108, 72, 43, 75, 36.1, 0.263, 33, tested_negative
0, 78, 88, 29, 40, 36.9, 0.434, 21, tested_negative
0, 107, 62, 30, 74, 36.6, 0.757, 25, tested_positive
2, 128, 78, 37, 182, 43.3, 1.224, 31, tested_positive
1, 128, 48, 45, 194, 40.5, 0.613, 24, tested_positive
0, 161, 50, 0, 0, 21.9, 0.254, 65, tested_negative
6, 151, 62, 31, 120, 35.5, 0.692, 28, tested_negative
2, 146, 70, 38, 360, 28, 0.337, 29, tested_positive
0, 126, 84, 29, 215, 30.7, 0.52, 24, tested_negative
14, 100, 78, 25, 184, 36.6, 0.412, 46, tested_positive
8, 112, 72, 0, 0, 23.6, 0.84, 58, tested_negative
0, 167, 0, 0, 0, 32.3, 0.839, 30, tested_positive
2, 144, 58, 33, 135, 31.6, 0.422, 25, tested_positive
5, 77, 82, 41, 42, 35.8, 0.156, 35, tested_negative
5, 115, 98, 0, 0, 52.9, 0.209, 28, tested_positive
3, 150, 76, 0, 0, 21, 0.207, 37, tested_negative
2, 120, 76, 37, 105, 39.7, 0.215, 29, tested_negative
10, 161, 68, 23, 132, 25.5, 0.326, 47, tested_positive
0, 137, 68, 14, 148, 24.8, 0.143, 21, tested_negative
0, 128, 68, 19, 180, 30.5, 1.391, 25, tested_positive
2, 124, 68, 28, 205, 32.9, 0.875, 30, tested_positive
6, 80, 66, 30, 0, 26.2, 0.313, 41, tested_negative
0, 106, 70, 37, 148, 39.4, 0.605, 22, tested_negative
2, 155, 74, 17, 96, 26.6, 0.433, 27, tested_positive
3, 113, 50, 10, 85, 29.5, 0.626, 25, tested_negative
7, 109, 80, 31, 0, 35.9, 1.127, 43, tested_positive
2, 112, 68, 22, 94, 34.1, 0.315, 26, tested_negative
3, 99, 80, 11, 64, 19.3, 0.284, 30, tested_negative
3, 182, 74, 0, 0, 30.5, 0.345, 29, tested_positive
3, 115, 66, 39, 140, 38.1, 0.15, 28, tested_negative
6, 194, 78, 0, 0, 23.5, 0.129, 59, tested_positive
4, 129, 60, 12, 231, 27.5, 0.527, 31, tested_negative
3, 112, 74, 30, 0, 31.6, 0.197, 25, tested_positive
0, 124, 70, 20, 0, 27.4, 0.254, 36, tested_positive
13, 152, 90, 33, 29, 26.8, 0.731, 43, tested_positive
2, 112, 75, 32, 0, 35.7, 0.148, 21, tested_negative
1, 157, 72, 21, 168, 25.6, 0.123, 24, tested_negative
1, 122, 64, 32, 156, 35.1, 0.692, 30, tested_positive
10, 179, 70, 0, 0, 35.1, 0.2, 37, tested_negative
2, 102, 86, 36, 120, 45.5, 0.127, 23, tested_positive
6, 105, 70, 32, 68, 30.8, 0.122, 37, tested_negative
8, 118, 72, 19, 0, 23.1, 1.476, 46, tested_negative
2, 87, 58, 16, 52, 32.7, 0.166, 25, tested_negative
1, 180, 0, 0, 0, 43.3, 0.282, 41, tested_positive
12, 106, 80, 0, 0, 23.6, 0.137, 44, tested_negative
1, 95, 60, 18, 58, 23.9, 0.26, 22, tested_negative
0, 165, 76, 43, 255, 47.9, 0.259, 26, tested_negative
0, 117, 0, 0, 0, 33.8, 0.932, 44, tested_negative
5, 115, 76, 0, 0, 31.2, 0.343, 44, tested_positive
9, 152, 78, 34, 171, 34.2, 0.893, 33, tested_positive
7, 178, 84, 0, 0, 39.9, 0.331, 41, tested_positive
1, 130, 70, 13, 105, 25.9, 0.472, 22, tested_negative
1, 95, 74, 21, 73, 25.9, 0.673, 36, tested_negative
1, 0, 68, 35, 0, 32, 0.389, 22, tested_negative
5, 122, 86, 0, 0, 34.7, 0.29, 33, tested_negative
8, 95, 72, 0, 0, 36.8, 0.485, 57, tested_negative
8, 126, 88, 36, 108, 38.5, 0.349, 49, tested_negative
1, 139, 46, 19, 83, 28.7, 0.654, 22, tested_negative
3, 116, 0, 0, 0, 23.5, 0.187, 23, tested_negative
3, 99, 62, 19, 74, 21.8, 0.279, 26, tested_negative
5, 0, 80, 32, 0, 41, 0.346, 37, tested_positive
4, 92, 80, 0, 0, 42.2, 0.237, 29, tested_negative
4, 137, 84, 0, 0, 31.2, 0.252, 30, tested_negative
3, 61, 82, 28, 0, 34.4, 0.243, 46, tested_negative
1, 90, 62, 12, 43, 27.2, 0.58, 24, tested_negative
3, 90, 78, 0, 0, 42.7, 0.559, 21, tested_negative
9, 165, 88, 0, 0, 30.4, 0.302, 49, tested_positive
1, 125, 50, 40, 167, 33.3, 0.962, 28, tested_positive
13, 129, 0, 30, 0, 39.9, 0.569, 44, tested_positive
12, 88, 74, 40, 54, 35.3, 0.378, 48, tested_negative
1, 196, 76, 36, 249, 36.5, 0.875, 29, tested_positive
5, 189, 64, 33, 325, 31.2, 0.583, 29, tested_positive
5, 158, 70, 0, 0, 29.8, 0.207, 63, tested_negative
5, 103, 108, 37, 0, 39.2, 0.305, 65, tested_negative
4, 146, 78, 0, 0, 38.5, 0.52, 67, tested_positive
4, 147, 74, 25, 293, 34.9, 0.385, 30, tested_negative
5, 99, 54, 28, 83, 34, 0.499, 30, tested_negative
6, 124, 72, 0, 0, 27.6, 0.368, 29, tested_positive
0, 101, 64, 17, 0, 21, 0.252, 21, tested_negative
3, 81, 86, 16, 66, 27.5, 0.306, 22, tested_negative
1, 133, 102, 28, 140, 32.8, 0.234, 45, tested_positive
3, 173, 82, 48, 465, 38.4, 2.137, 25, tested_positive
0, 118, 64, 23, 89, 0, 1.731, 21, tested_negative
0, 84, 64, 22, 66, 35.8, 0.545, 21, tested_negative
2, 105, 58, 40, 94, 34.9, 0.225, 25, tested_negative
2, 122, 52, 43, 158, 36.2, 0.816, 28, tested_negative
12, 140, 82, 43, 325, 39.2, 0.528, 58, tested_positive
0, 98, 82, 15, 84, 25.2, 0.299, 22, tested_negative
1, 87, 60, 37, 75, 37.2, 0.509, 22, tested_negative
4, 156, 75, 0, 0, 48.3, 0.238, 32, tested_positive
0, 93, 100, 39, 72, 43.4, 1.021, 35, tested_negative
1, 107, 72, 30, 82, 30.8, 0.821, 24, tested_negative
0, 105, 68, 22, 0, 20, 0.236, 22, tested_negative
1, 109, 60, 8, 182, 25.4, 0.947, 21, tested_negative
1, 90, 62, 18, 59, 25.1, 1.268, 25, tested_negative
1, 125, 70, 24, 110, 24.3, 0.221, 25, tested_negative
1, 119, 54, 13, 50, 22.3, 0.205, 24, tested_negative
5, 116, 74, 29, 0, 32.3, 0.66, 35, tested_positive
8, 105, 100, 36, 0, 43.3, 0.239, 45, tested_positive
5, 144, 82, 26, 285, 32, 0.452, 58, tested_positive
3, 100, 68, 23, 81, 31.6, 0.949, 28, tested_negative
1, 100, 66, 29, 196, 32, 0.444, 42, tested_negative
5, 166, 76, 0, 0, 45.7, 0.34, 27, tested_positive
1, 131, 64, 14, 415, 23.7, 0.389, 21, tested_negative
4, 116, 72, 12, 87, 22.1, 0.463, 37, tested_negative
4, 158, 78, 0, 0, 32.9, 0.803, 31, tested_positive
2, 127, 58, 24, 275, 27.7, 1.6, 25, tested_negative
3, 96, 56, 34, 115, 24.7, 0.944, 39, tested_negative
0, 131, 66, 40, 0, 34.3, 0.196, 22, tested_positive
3, 82, 70, 0, 0, 21.1, 0.389, 25, tested_negative
3, 193, 70, 31, 0, 34.9, 0.241, 25, tested_positive
4, 95, 64, 0, 0, 32, 0.161, 31, tested_positive
6, 137, 61, 0, 0, 24.2, 0.151, 55, tested_negative
5, 136, 84, 41, 88, 35, 0.286, 35, tested_positive
9, 72, 78, 25, 0, 31.6, 0.28, 38, tested_negative
5, 168, 64, 0, 0, 32.9, 0.135, 41, tested_positive
2, 123, 48, 32, 165, 42.1, 0.52, 26, tested_negative
4, 115, 72, 0, 0, 28.9, 0.376, 46, tested_positive
0, 101, 62, 0, 0, 21.9, 0.336, 25, tested_negative
8, 197, 74, 0, 0, 25.9, 1.191, 39, tested_positive
1, 172, 68, 49, 579, 42.4, 0.702, 28, tested_positive
6, 102, 90, 39, 0, 35.7, 0.674, 28, tested_negative
1, 112, 72, 30, 176, 34.4, 0.528, 25, tested_negative
1, 143, 84, 23, 310, 42.4, 1.076, 22, tested_negative
1, 143, 74, 22, 61, 26.2, 0.256, 21, tested_negative
0, 138, 60, 35, 167, 34.6, 0.534, 21, tested_positive
3, 173, 84, 33, 474, 35.7, 0.258, 22, tested_positive
1, 97, 68, 21, 0, 27.2, 1.095, 22, tested_negative
4, 144, 82, 32, 0, 38.5, 0.554, 37, tested_positive
1, 83, 68, 0, 0, 18.2, 0.624, 27, tested_negative
3, 129, 64, 29, 115, 26.4, 0.219, 28, tested_positive
1, 119, 88, 41, 170, 45.3, 0.507, 26, tested_negative
2, 94, 68, 18, 76, 26, 0.561, 21, tested_negative
0, 102, 64, 46, 78, 40.6, 0.496, 21, tested_negative
2, 115, 64, 22, 0, 30.8, 0.421, 21, tested_negative
8, 151, 78, 32, 210, 42.9, 0.516, 36, tested_positive
4, 184, 78, 39, 277, 37, 0.264, 31, tested_positive
0, 94, 0, 0, 0, 0, 0.256, 25, tested_negative
1, 181, 64, 30, 180, 34.1, 0.328, 38, tested_positive
0, 135, 94, 46, 145, 40.6, 0.284, 26, tested_negative
1, 95, 82, 25, 180, 35, 0.233, 43, tested_positive
2, 99, 0, 0, 0, 22.2, 0.108, 23, tested_negative
3, 89, 74, 16, 85, 30.4, 0.551, 38, tested_negative
1, 80, 74, 11, 60, 30, 0.527, 22, tested_negative
2, 139, 75, 0, 0, 25.6, 0.167, 29, tested_negative
1, 90, 68, 8, 0, 24.5, 1.138, 36, tested_negative
0, 141, 0, 0, 0, 42.4, 0.205, 29, tested_positive
12, 140, 85, 33, 0, 37.4, 0.244, 41, tested_negative
5, 147, 75, 0, 0, 29.9, 0.434, 28, tested_negative
1, 97, 70, 15, 0, 18.2, 0.147, 21, tested_negative
6, 107, 88, 0, 0, 36.8, 0.727, 31, tested_negative
0, 189, 104, 25, 0, 34.3, 0.435, 41, tested_positive
2, 83, 66, 23, 50, 32.2, 0.497, 22, tested_negative
4, 117, 64, 27, 120, 33.2, 0.23, 24, tested_negative
8, 108, 70, 0, 0, 30.5, 0.955, 33, tested_positive
4, 117, 62, 12, 0, 29.7, 0.38, 30, tested_positive
0, 180, 78, 63, 14, 59.4, 2.42, 25, tested_positive
1, 100, 72, 12, 70, 25.3, 0.658, 28, tested_negative
0, 95, 80, 45, 92, 36.5, 0.33, 26, tested_negative
0, 104, 64, 37, 64, 33.6, 0.51, 22, tested_positive
0, 120, 74, 18, 63, 30.5, 0.285, 26, tested_negative
1, 82, 64, 13, 95, 21.2, 0.415, 23, tested_negative
2, 134, 70, 0, 0, 28.9, 0.542, 23, tested_positive
0, 91, 68, 32, 210, 39.9, 0.381, 25, tested_negative
2, 119, 0, 0, 0, 19.6, 0.832, 72, tested_negative
2, 100, 54, 28, 105, 37.8, 0.498, 24, tested_negative
14, 175, 62, 30, 0, 33.6, 0.212, 38, tested_positive
1, 135, 54, 0, 0, 26.7, 0.687, 62, tested_negative
5, 86, 68, 28, 71, 30.2, 0.364, 24, tested_negative
10, 148, 84, 48, 237, 37.6, 1.001, 51, tested_positive
9, 134, 74, 33, 60, 25.9, 0.46, 81, tested_negative
9, 120, 72, 22, 56, 20.8, 0.733, 48, tested_negative
1, 71, 62, 0, 0, 21.8, 0.416, 26, tested_negative
8, 74, 70, 40, 49, 35.3, 0.705, 39, tested_negative
5, 88, 78, 30, 0, 27.6, 0.258, 37, tested_negative
10, 115, 98, 0, 0, 24, 1.022, 34, tested_negative
0, 124, 56, 13, 105, 21.8, 0.452, 21, tested_negative
0, 74, 52, 10, 36, 27.8, 0.269, 22, tested_negative
0, 97, 64, 36, 100, 36.8, 0.6, 25, tested_negative
8, 120, 0, 0, 0, 30, 0.183, 38, tested_positive
6, 154, 78, 41, 140, 46.1, 0.571, 27, tested_negative
1, 144, 82, 40, 0, 41.3, 0.607, 28, tested_negative
0, 137, 70, 38, 0, 33.2, 0.17, 22, tested_negative
0, 119, 66, 27, 0, 38.8, 0.259, 22, tested_negative
7, 136, 90, 0, 0, 29.9, 0.21, 50, tested_negative
4, 114, 64, 0, 0, 28.9, 0.126, 24, tested_negative
0, 137, 84, 27, 0, 27.3, 0.231, 59, tested_negative
2, 105, 80, 45, 191, 33.7, 0.711, 29, tested_positive
7, 114, 76, 17, 110, 23.8, 0.466, 31, tested_negative
8, 126, 74, 38, 75, 25.9, 0.162, 39, tested_negative
4, 132, 86, 31, 0, 28, 0.419, 63, tested_negative
3, 158, 70, 30, 328, 35.5, 0.344, 35, tested_positive
0, 123, 88, 37, 0, 35.2, 0.197, 29, tested_negative
4, 85, 58, 22, 49, 27.8, 0.306, 28, tested_negative
0, 84, 82, 31, 125, 38.2, 0.233, 23, tested_negative
0, 145, 0, 0, 0, 44.2, 0.63, 31, tested_positive
0, 135, 68, 42, 250, 42.3, 0.365, 24, tested_positive
1, 139, 62, 41, 480, 40.7, 0.536, 21, tested_negative
0, 173, 78, 32, 265, 46.5, 1.159, 58, tested_negative
4, 99, 72, 17, 0, 25.6, 0.294, 28, tested_negative
8, 194, 80, 0, 0, 26.1, 0.551, 67, tested_negative
2, 83, 65, 28, 66, 36.8, 0.629, 24, tested_negative
2, 89, 90, 30, 0, 33.5, 0.292, 42, tested_negative
4, 99, 68, 38, 0, 32.8, 0.145, 33, tested_negative
4, 125, 70, 18, 122, 28.9, 1.144, 45, tested_positive
3, 80, 0, 0, 0, 0, 0.174, 22, tested_negative
6, 166, 74, 0, 0, 26.6, 0.304, 66, tested_negative
5, 110, 68, 0, 0, 26, 0.292, 30, tested_negative
2, 81, 72, 15, 76, 30.1, 0.547, 25, tested_negative
7, 195, 70, 33, 145, 25.1, 0.163, 55, tested_positive
6, 154, 74, 32, 193, 29.3, 0.839, 39, tested_negative
2, 117, 90, 19, 71, 25.2, 0.313, 21, tested_negative
3, 84, 72, 32, 0, 37.2, 0.267, 28, tested_negative
6, 0, 68, 41, 0, 39, 0.727, 41, tested_positive
7, 94, 64, 25, 79, 33.3, 0.738, 41, tested_negative
3, 96, 78, 39, 0, 37.3, 0.238, 40, tested_negative
10, 75, 82, 0, 0, 33.3, 0.263, 38, tested_negative
0, 180, 90, 26, 90, 36.5, 0.314, 35, tested_positive
1, 130, 60, 23, 170, 28.6, 0.692, 21, tested_negative
2, 84, 50, 23, 76, 30.4, 0.968, 21, tested_negative
8, 120, 78, 0, 0, 25, 0.409, 64, tested_negative
12, 84, 72, 31, 0, 29.7, 0.297, 46, tested_positive
0, 139, 62, 17, 210, 22.1, 0.207, 21, tested_negative
9, 91, 68, 0, 0, 24.2, 0.2, 58, tested_negative
2, 91, 62, 0, 0, 27.3, 0.525, 22, tested_negative
3, 99, 54, 19, 86, 25.6, 0.154, 24, tested_negative
3, 163, 70, 18, 105, 31.6, 0.268, 28, tested_positive
9, 145, 88, 34, 165, 30.3, 0.771, 53, tested_positive
7, 125, 86, 0, 0, 37.6, 0.304, 51, tested_negative
13, 76, 60, 0, 0, 32.8, 0.18, 41, tested_negative
6, 129, 90, 7, 326, 19.6, 0.582, 60, tested_negative
2, 68, 70, 32, 66, 25, 0.187, 25, tested_negative
3, 124, 80, 33, 130, 33.2, 0.305, 26, tested_negative
6, 114, 0, 0, 0, 0, 0.189, 26, tested_negative
9, 130, 70, 0, 0, 34.2, 0.652, 45, tested_positive
3, 125, 58, 0, 0, 31.6, 0.151, 24, tested_negative
3, 87, 60, 18, 0, 21.8, 0.444, 21, tested_negative
1, 97, 64, 19, 82, 18.2, 0.299, 21, tested_negative
3, 116, 74, 15, 105, 26.3, 0.107, 24, tested_negative
0, 117, 66, 31, 188, 30.8, 0.493, 22, tested_negative
0, 111, 65, 0, 0, 24.6, 0.66, 31, tested_negative
2, 122, 60, 18, 106, 29.8, 0.717, 22, tested_negative
0, 107, 76, 0, 0, 45.3, 0.686, 24, tested_negative
1, 86, 66, 52, 65, 41.3, 0.917, 29, tested_negative
6, 91, 0, 0, 0, 29.8, 0.501, 31, tested_negative
1, 77, 56, 30, 56, 33.3, 1.251, 24, tested_negative
4, 132, 0, 0, 0, 32.9, 0.302, 23, tested_positive
0, 105, 90, 0, 0, 29.6, 0.197, 46, tested_negative
0, 57, 60, 0, 0, 21.7, 0.735, 67, tested_negative
0, 127, 80, 37, 210, 36.3, 0.804, 23, tested_negative
3, 129, 92, 49, 155, 36.4, 0.968, 32, tested_positive
8, 100, 74, 40, 215, 39.4, 0.661, 43, tested_positive
3, 128, 72, 25, 190, 32.4, 0.549, 27, tested_positive
10, 90, 85, 32, 0, 34.9, 0.825, 56, tested_positive
4, 84, 90, 23, 56, 39.5, 0.159, 25, tested_negative
1, 88, 78, 29, 76, 32, 0.365, 29, tested_negative
8, 186, 90, 35, 225, 34.5, 0.423, 37, tested_positive
5, 187, 76, 27, 207, 43.6, 1.034, 53, tested_positive
4, 131, 68, 21, 166, 33.1, 0.16, 28, tested_negative
1, 164, 82, 43, 67, 32.8, 0.341, 50, tested_negative
4, 189, 110, 31, 0, 28.5, 0.68, 37, tested_negative
1, 116, 70, 28, 0, 27.4, 0.204, 21, tested_negative
3, 84, 68, 30, 106, 31.9, 0.591, 25, tested_negative
6, 114, 88, 0, 0, 27.8, 0.247, 66, tested_negative
1, 88, 62, 24, 44, 29.9, 0.422, 23, tested_negative
1, 84, 64, 23, 115, 36.9, 0.471, 28, tested_negative
7, 124, 70, 33, 215, 25.5, 0.161, 37, tested_negative
1, 97, 70, 40, 0, 38.1, 0.218, 30, tested_negative
8, 110, 76, 0, 0, 27.8, 0.237, 58, tested_negative
11, 103, 68, 40, 0, 46.2, 0.126, 42, tested_negative
11, 85, 74, 0, 0, 30.1, 0.3, 35, tested_negative
6, 125, 76, 0, 0, 33.8, 0.121, 54, tested_positive
0, 198, 66, 32, 274, 41.3, 0.502, 28, tested_positive
1, 87, 68, 34, 77, 37.6, 0.401, 24, tested_negative
6, 99, 60, 19, 54, 26.9, 0.497, 32, tested_negative
0, 91, 80, 0, 0, 32.4, 0.601, 27, tested_negative
2, 95, 54, 14, 88, 26.1, 0.748, 22, tested_negative
1, 99, 72, 30, 18, 38.6, 0.412, 21, tested_negative
6, 92, 62, 32, 126, 32, 0.085, 46, tested_negative
4, 154, 72, 29, 126, 31.3, 0.338, 37, tested_negative
0, 121, 66, 30, 165, 34.3, 0.203, 33, tested_positive
3, 78, 70, 0, 0, 32.5, 0.27, 39, tested_negative
2, 130, 96, 0, 0, 22.6, 0.268, 21, tested_negative
3, 111, 58, 31, 44, 29.5, 0.43, 22, tested_negative
2, 98, 60, 17, 120, 34.7, 0.198, 22, tested_negative
1, 143, 86, 30, 330, 30.1, 0.892, 23, tested_negative
1, 119, 44, 47, 63, 35.5, 0.28, 25, tested_negative
6, 108, 44, 20, 130, 24, 0.813, 35, tested_negative
2, 118, 80, 0, 0, 42.9, 0.693, 21, tested_positive
10, 133, 68, 0, 0, 27, 0.245, 36, tested_negative
2, 197, 70, 99, 0, 34.7, 0.575, 62, tested_positive
0, 151, 90, 46, 0, 42.1, 0.371, 21, tested_positive
6, 109, 60, 27, 0, 25, 0.206, 27, tested_negative
12, 121, 78, 17, 0, 26.5, 0.259, 62, tested_negative
8, 100, 76, 0, 0, 38.7, 0.19, 42, tested_negative
8, 124, 76, 24, 600, 28.7, 0.687, 52, tested_positive
1, 93, 56, 11, 0, 22.5, 0.417, 22, tested_negative
8, 143, 66, 0, 0, 34.9, 0.129, 41, tested_positive
6, 103, 66, 0, 0, 24.3, 0.249, 29, tested_negative
3, 176, 86, 27, 156, 33.3, 1.154, 52, tested_positive
0, 73, 0, 0, 0, 21.1, 0.342, 25, tested_negative
11, 111, 84, 40, 0, 46.8, 0.925, 45, tested_positive
2, 112, 78, 50, 140, 39.4, 0.175, 24, tested_negative
3, 132, 80, 0, 0, 34.4, 0.402, 44, tested_positive
2, 82, 52, 22, 115, 28.5, 1.699, 25, tested_negative
6, 123, 72, 45, 230, 33.6, 0.733, 34, tested_negative
0, 188, 82, 14, 185, 32, 0.682, 22, tested_positive
0, 67, 76, 0, 0, 45.3, 0.194, 46, tested_negative
1, 89, 24, 19, 25, 27.8, 0.559, 21, tested_negative
1, 173, 74, 0, 0, 36.8, 0.088, 38, tested_positive
1, 109, 38, 18, 120, 23.1, 0.407, 26, tested_negative
1, 108, 88, 19, 0, 27.1, 0.4, 24, tested_negative
6, 96, 0, 0, 0, 23.7, 0.19, 28, tested_negative
1, 124, 74, 36, 0, 27.8, 0.1, 30, tested_negative
7, 150, 78, 29, 126, 35.2, 0.692, 54, tested_positive
4, 183, 0, 0, 0, 28.4, 0.212, 36, tested_positive
1, 124, 60, 32, 0, 35.8, 0.514, 21, tested_negative
1, 181, 78, 42, 293, 40, 1.258, 22, tested_positive
1, 92, 62, 25, 41, 19.5, 0.482, 25, tested_negative
0, 152, 82, 39, 272, 41.5, 0.27, 27, tested_negative
1, 111, 62, 13, 182, 24, 0.138, 23, tested_negative
3, 106, 54, 21, 158, 30.9, 0.292, 24, tested_negative
3, 174, 58, 22, 194, 32.9, 0.593, 36, tested_positive
7, 168, 88, 42, 321, 38.2, 0.787, 40, tested_positive
6, 105, 80, 28, 0, 32.5, 0.878, 26, tested_negative
11, 138, 74, 26, 144, 36.1, 0.557, 50, tested_positive
3, 106, 72, 0, 0, 25.8, 0.207, 27, tested_negative
6, 117, 96, 0, 0, 28.7, 0.157, 30, tested_negative
2, 68, 62, 13, 15, 20.1, 0.257, 23, tested_negative
9, 112, 82, 24, 0, 28.2, 1.282, 50, tested_positive
0, 119, 0, 0, 0, 32.4, 0.141, 24, tested_positive
2, 112, 86, 42, 160, 38.4, 0.246, 28, tested_negative
2, 92, 76, 20, 0, 24.2, 1.698, 28, tested_negative
6, 183, 94, 0, 0, 40.8, 1.461, 45, tested_negative
0, 94, 70, 27, 115, 43.5, 0.347, 21, tested_negative
2, 108, 64, 0, 0, 30.8, 0.158, 21, tested_negative
4, 90, 88, 47, 54, 37.7, 0.362, 29, tested_negative
0, 125, 68, 0, 0, 24.7, 0.206, 21, tested_negative
0, 132, 78, 0, 0, 32.4, 0.393, 21, tested_negative
5, 128, 80, 0, 0, 34.6, 0.144, 45, tested_negative
4, 94, 65, 22, 0, 24.7, 0.148, 21, tested_negative
7, 114, 64, 0, 0, 27.4, 0.732, 34, tested_positive
0, 102, 78, 40, 90, 34.5, 0.238, 24, tested_negative
2, 111, 60, 0, 0, 26.2, 0.343, 23, tested_negative
1, 128, 82, 17, 183, 27.5, 0.115, 22, tested_negative
10, 92, 62, 0, 0, 25.9, 0.167, 31, tested_negative
13, 104, 72, 0, 0, 31.2, 0.465, 38, tested_positive
5, 104, 74, 0, 0, 28.8, 0.153, 48, tested_negative
2, 94, 76, 18, 66, 31.6, 0.649, 23, tested_negative
7, 97, 76, 32, 91, 40.9, 0.871, 32, tested_positive
1, 100, 74, 12, 46, 19.5, 0.149, 28, tested_negative
0, 102, 86, 17, 105, 29.3, 0.695, 27, tested_negative
4, 128, 70, 0, 0, 34.3, 0.303, 24, tested_negative
6, 147, 80, 0, 0, 29.5, 0.178, 50, tested_positive
4, 90, 0, 0, 0, 28, 0.61, 31, tested_negative
3, 103, 72, 30, 152, 27.6, 0.73, 27, tested_negative
2, 157, 74, 35, 440, 39.4, 0.134, 30, tested_negative
1, 167, 74, 17, 144, 23.4, 0.447, 33, tested_positive
0, 179, 50, 36, 159, 37.8, 0.455, 22, tested_positive
11, 136, 84, 35, 130, 28.3, 0.26, 42, tested_positive
0, 107, 60, 25, 0, 26.4, 0.133, 23, tested_negative
1, 91, 54, 25, 100, 25.2, 0.234, 23, tested_negative
1, 117, 60, 23, 106, 33.8, 0.466, 27, tested_negative
5, 123, 74, 40, 77, 34.1, 0.269, 28, tested_negative
2, 120, 54, 0, 0, 26.8, 0.455, 27, tested_negative
1, 106, 70, 28, 135, 34.2, 0.142, 22, tested_negative
2, 155, 52, 27, 540, 38.7, 0.24, 25, tested_positive
2, 101, 58, 35, 90, 21.8, 0.155, 22, tested_negative
1, 120, 80, 48, 200, 38.9, 1.162, 41, tested_negative
11, 127, 106, 0, 0, 39, 0.19, 51, tested_negative
3, 80, 82, 31, 70, 34.2, 1.292, 27, tested_positive
10, 162, 84, 0, 0, 27.7, 0.182, 54, tested_negative
1, 199, 76, 43, 0, 42.9, 1.394, 22, tested_positive
8, 167, 106, 46, 231, 37.6, 0.165, 43, tested_positive
9, 145, 80, 46, 130, 37.9, 0.637, 40, tested_positive
6, 115, 60, 39, 0, 33.7, 0.245, 40, tested_positive
1, 112, 80, 45, 132, 34.8, 0.217, 24, tested_negative
4, 145, 82, 18, 0, 32.5, 0.235, 70, tested_positive
10, 111, 70, 27, 0, 27.5, 0.141, 40, tested_positive
6, 98, 58, 33, 190, 34, 0.43, 43, tested_negative
9, 154, 78, 30, 100, 30.9, 0.164, 45, tested_negative
6, 165, 68, 26, 168, 33.6, 0.631, 49, tested_negative
1, 99, 58, 10, 0, 25.4, 0.551, 21, tested_negative
10, 68, 106, 23, 49, 35.5, 0.285, 47, tested_negative
3, 123, 100, 35, 240, 57.3, 0.88, 22, tested_negative
8, 91, 82, 0, 0, 35.6, 0.587, 68, tested_negative
6, 195, 70, 0, 0, 30.9, 0.328, 31, tested_positive
9, 156, 86, 0, 0, 24.8, 0.23, 53, tested_positive
0, 93, 60, 0, 0, 35.3, 0.263, 25, tested_negative
3, 121, 52, 0, 0, 36, 0.127, 25, tested_positive
2, 101, 58, 17, 265, 24.2, 0.614, 23, tested_negative
2, 56, 56, 28, 45, 24.2, 0.332, 22, tested_negative
0, 162, 76, 36, 0, 49.6, 0.364, 26, tested_positive
0, 95, 64, 39, 105, 44.6, 0.366, 22, tested_negative
4, 125, 80, 0, 0, 32.3, 0.536, 27, tested_positive
5, 136, 82, 0, 0, 0, 0.64, 69, tested_negative
2, 129, 74, 26, 205, 33.2, 0.591, 25, tested_negative
3, 130, 64, 0, 0, 23.1, 0.314, 22, tested_negative
1, 107, 50, 19, 0, 28.3, 0.181, 29, tested_negative
1, 140, 74, 26, 180, 24.1, 0.828, 23, tested_negative
1, 144, 82, 46, 180, 46.1, 0.335, 46, tested_positive
8, 107, 80, 0, 0, 24.6, 0.856, 34, tested_negative
13, 158, 114, 0, 0, 42.3, 0.257, 44, tested_positive
2, 121, 70, 32, 95, 39.1, 0.886, 23, tested_negative
7, 129, 68, 49, 125, 38.5, 0.439, 43, tested_positive
2, 90, 60, 0, 0, 23.5, 0.191, 25, tested_negative
7, 142, 90, 24, 480, 30.4, 0.128, 43, tested_positive
3, 169, 74, 19, 125, 29.9, 0.268, 31, tested_positive
0, 99, 0, 0, 0, 25, 0.253, 22, tested_negative
4, 127, 88, 11, 155, 34.5, 0.598, 28, tested_negative
4, 118, 70, 0, 0, 44.5, 0.904, 26, tested_negative
2, 122, 76, 27, 200, 35.9, 0.483, 26, tested_negative
6, 125, 78, 31, 0, 27.6, 0.565, 49, tested_positive
1, 168, 88, 29, 0, 35, 0.905, 52, tested_positive
2, 129, 0, 0, 0, 38.5, 0.304, 41, tested_negative
4, 110, 76, 20, 100, 28.4, 0.118, 27, tested_negative
6, 80, 80, 36, 0, 39.8, 0.177, 28, tested_negative
10, 115, 0, 0, 0, 0, 0.261, 30, tested_positive
2, 127, 46, 21, 335, 34.4, 0.176, 22, tested_negative
9, 164, 78, 0, 0, 32.8, 0.148, 45, tested_positive
2, 93, 64, 32, 160, 38, 0.674, 23, tested_positive
3, 158, 64, 13, 387, 31.2, 0.295, 24, tested_negative
5, 126, 78, 27, 22, 29.6, 0.439, 40, tested_negative
10, 129, 62, 36, 0, 41.2, 0.441, 38, tested_positive
0, 134, 58, 20, 291, 26.4, 0.352, 21, tested_negative
3, 102, 74, 0, 0, 29.5, 0.121, 32, tested_negative
7, 187, 50, 33, 392, 33.9, 0.826, 34, tested_positive
3, 173, 78, 39, 185, 33.8, 0.97, 31, tested_positive
10, 94, 72, 18, 0, 23.1, 0.595, 56, tested_negative
1, 108, 60, 46, 178, 35.5, 0.415, 24, tested_negative
5, 97, 76, 27, 0, 35.6, 0.378, 52, tested_positive
4, 83, 86, 19, 0, 29.3, 0.317, 34, tested_negative
1, 114, 66, 36, 200, 38.1, 0.289, 21, tested_negative
1, 149, 68, 29, 127, 29.3, 0.349, 42, tested_positive
5, 117, 86, 30, 105, 39.1, 0.251, 42, tested_negative
1, 111, 94, 0, 0, 32.8, 0.265, 45, tested_negative
4, 112, 78, 40, 0, 39.4, 0.236, 38, tested_negative
1, 116, 78, 29, 180, 36.1, 0.496, 25, tested_negative
0, 141, 84, 26, 0, 32.4, 0.433, 22, tested_negative
2, 175, 88, 0, 0, 22.9, 0.326, 22, tested_negative
2, 92, 52, 0, 0, 30.1, 0.141, 22, tested_negative
3, 130, 78, 23, 79, 28.4, 0.323, 34, tested_positive
8, 120, 86, 0, 0, 28.4, 0.259, 22, tested_positive
2, 174, 88, 37, 120, 44.5, 0.646, 24, tested_positive
2, 106, 56, 27, 165, 29, 0.426, 22, tested_negative
2, 105, 75, 0, 0, 23.3, 0.56, 53, tested_negative
4, 95, 60, 32, 0, 35.4, 0.284, 28, tested_negative
0, 126, 86, 27, 120, 27.4, 0.515, 21, tested_negative
8, 65, 72, 23, 0, 32, 0.6, 42, tested_negative
2, 99, 60, 17, 160, 36.6, 0.453, 21, tested_negative
1, 102, 74, 0, 0, 39.5, 0.293, 42, tested_positive
11, 120, 80, 37, 150, 42.3, 0.785, 48, tested_positive
3, 102, 44, 20, 94, 30.8, 0.4, 26, tested_negative
1, 109, 58, 18, 116, 28.5, 0.219, 22, tested_negative
9, 140, 94, 0, 0, 32.7, 0.734, 45, tested_positive
13, 153, 88, 37, 140, 40.6, 1.174, 39, tested_negative
12, 100, 84, 33, 105, 30, 0.488, 46, tested_negative
1, 147, 94, 41, 0, 49.3, 0.358, 27, tested_positive
1, 81, 74, 41, 57, 46.3, 1.096, 32, tested_negative
3, 187, 70, 22, 200, 36.4, 0.408, 36, tested_positive
6, 162, 62, 0, 0, 24.3, 0.178, 50, tested_positive
4, 136, 70, 0, 0, 31.2, 1.182, 22, tested_positive
1, 121, 78, 39, 74, 39, 0.261, 28, tested_negative
3, 108, 62, 24, 0, 26, 0.223, 25, tested_negative
0, 181, 88, 44, 510, 43.3, 0.222, 26, tested_positive
8, 154, 78, 32, 0, 32.4, 0.443, 45, tested_positive
1, 128, 88, 39, 110, 36.5, 1.057, 37, tested_positive
7, 137, 90, 41, 0, 32, 0.391, 39, tested_negative
0, 123, 72, 0, 0, 36.3, 0.258, 52, tested_positive
1, 106, 76, 0, 0, 37.5, 0.197, 26, tested_negative
6, 190, 92, 0, 0, 35.5, 0.278, 66, tested_positive
2, 88, 58, 26, 16, 28.4, 0.766, 22, tested_negative
9, 170, 74, 31, 0, 44, 0.403, 43, tested_positive
9, 89, 62, 0, 0, 22.5, 0.142, 33, tested_negative
10, 101, 76, 48, 180, 32.9, 0.171, 63, tested_negative
2, 122, 70, 27, 0, 36.8, 0.34, 27, tested_negative
5, 121, 72, 23, 112, 26.2, 0.245, 30, tested_negative
1, 126, 60, 0, 0, 30.1, 0.349, 47, tested_positive
1, 93, 70, 31, 0, 30.4, 0.315, 23, tested_negative
"""

if __name__ == '__main__':
  my = opt(docopt(__doc__), s=int, k=int)
  seed(my.s)
  print(my.r)
  test_tab2()
