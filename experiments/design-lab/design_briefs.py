"""Briefs for the design experiment. A gives an open creative brief; B gives a full art direction plus a technique cookbook."""

SUBJECT = ("Rollwise is a free label roll calculator for small-batch makers (candles, soap, jars, sauces) who "
           "print product labels on rolls. Visitors enter their batch and roll size and learn how many label "
           "rolls to order. It runs entirely in the browser with no ads and no tracking.")

CONSTRAINTS = """HOW THIS WORKS: you only edit files. You cannot run commands, servers, builds or previews, so do not try,
and do not create helper scripts, notes or other extra files. When you finish, the system builds, tests and
screenshots your work automatically.

THE CALCULATOR IS LOCKED: its working markup (form, inputs, button, result, roll strip and live regions) lives in
src/components/Calculator.astro. Read it to learn its structure, but you cannot edit it. index.astro renders it
with <Calculator />. You may wrap <Calculator /> in your own elements and place decoration around it. Restyle all
of it from CSS, using its classes: .sheet .planner .planner-intro .fields .allowance .help .field-error .live-hint
.result-kind .answer .enough .strip .legend .key .key-order .key-have .key-spare .note .visually-hidden, and its
ids: #planner #result #order #order-label #enough #strip #roll-caption #needed #required #left #error, plus
button, input, label, output, dl, dt, dd.

HARD RULES. Breaking any of them gets your work rejected automatically:
1. Edit only these files: src/pages/index.astro, src/pages/privacy.astro, any src/styles/*.css, and any
   src/components/*.astro except Calculator.astro. You may create new .css and .astro files in those folders.
   Never edit tests, scripts, src/lib, src/scripts, Calculator.astro, config or package files. Never read
   node_modules.
2. Keep these in index.astro: <Calculator /> and its import line, the <title> text, the phrase "No inputs leave
   your browser", the line <meta name="robots" content={config.robots} />, the canonical link and its const,
   lang="en" and the meta description. Keep everything in the <head> of index.astro and privacy.astro as it is.
   The calculator script loads from Calculator.astro, so do not add script tags anywhere.
3. No new <script> tags, no external URLs, no remote fonts or images, and no CSS @import. CSS url() may only use
   data: URIs (inline SVG or noise is fine). Inline <svg> markup in .astro files is fine.
4. Fonts: you may import extra weights from the installed packages in the frontmatter of index.astro, for example
   import '@fontsource/bricolage-grotesque/latin-800.css'; (weights 200-800) or
   import '@fontsource/source-sans-3/latin-700.css'; (200-900). No other fonts exist.
5. Accessibility is scored: body text at least 16px with 4.5:1 contrast (large text 3:1), a visible focus style,
   motion only inside @media (prefers-reduced-motion: no-preference), and no sideways scrolling at 390px width.
   Never set dark text on a dark band or light text on a light one; a section that changes its background must
   also set its own text colour. Nothing may sit on top of the calculator at any width: the tests tap every field
   and the Calculate button on a 393px-wide phone, so decorative layers need pointer-events: none and must sit
   behind the content, and grid areas and absolutely positioned pieces must not overlap the form.
6. calculator.ts draws the roll strip as span elements with classes .roll, .roll.order, .roll.have and
   .roll.partial (which uses the CSS variable --used, a percentage), plus .more. Restyle them as you like, but keep
   them visible.
Work with Read, Write and Edit. For a large redesign it is easiest to Write whole files. Tool parameters are
strict: Write takes exactly file_path and content; Edit takes exactly file_path, old_string, new_string and
optionally replace_all. Any other parameter, such as reason, makes the call fail and saves nothing. When you finish, reply with
a short summary of the design.
Work through every part of the brief in this session. Do not stop to describe next steps; make the edits.
When everything is built, end your final reply with the single word DONE."""

OPEN_BRIEF = f"""You are a world-class web designer whose sites win Awwwards Site of the Day. Redesign this website so it
is visually stunning: a bold concept, a signature visual idea, memorable typography, rich detail and tasteful
motion. It must still feel right for its audience and keep the calculator easy to use. The current design is
clean but plain, and plain is a failure here.

Site: {SUBJECT}

Start by reading src/pages/index.astro, src/components/Calculator.astro, src/styles/site.css,
src/components/SiteHeader.astro and src/components/SiteFooter.astro. Then redesign.

{CONSTRAINTS}"""

ART_DIRECTION = """ART DIRECTION: "PRESS CHECK"
Concept: the moment a printer pulls the first sheet off the press and checks it under the light. The whole site is
a press sheet: registration marks, CMYK colour bars, halftone, crop marks and slightly off-register ink. Its hero
image is a giant label roll that unspools a strip of labels toward the calculator.

Palette (use CSS custom properties):
--sheet #f5f7f9 (cool press-sheet white, never cream); --ink #101418 (all body text); --plate #1b2a8f (deep plate
blue for one full-width band, white text on it); --cyan #00a6e2, --magenta #e5007d, --yellow #ffe100 (process
inks: decoration, marks and large display only, never small text, and never yellow on white);
--rule #c9d1d8 (hairlines). The headline is solid --ink with cyan and magenta offset ghosts behind it.

Type: Bricolage Grotesque 800 for display, huge and tight (clamp(3.4rem, 9vw, 8.5rem), letter-spacing -0.045em,
line-height 0.9). Use it again for the result numeral at 7-9rem in --magenta. Source Sans 3 400/600/700 for
everything else at 17-19px. Small technical labels use Source Sans 3 600 at 13px uppercase with 0.12em spacing,
like press-sheet slug text.

Layout, top to bottom:
1. A full-width CMYK colour bar strip (about 10 squares: C, M, Y, K, then 75/50/25% tints) across the very top,
   with registration crosshairs at both ends.
2. Header: wordmark "Rollwise" plus slug text "PRESS SHEET 01 · LABEL ROLL CALCULATOR".
3. Hero, two columns on desktop: on the left the huge headline with off-register ghosts, the lede and the
   "No inputs leave your browser" line set as a slug; on the right the calculator, styled as a JOB TICKET. On the
   section background, behind and below the headline, a large inline-SVG label roll (concentric rings, a dark
   core, a halftone shadow) with a strip of small rounded-rectangle labels unspooling diagonally toward the ticket.
4. The job ticket: a white card with die-cut notched corners (made with a CSS mask), a 2px --ink border, a
   perforated tear line (a row of dots) between the form and the result stub (draw it in CSS, for example with
   output#result::before, because the calculator markup is locked), and a rotated "PROOF" stamp in magenta on
   preview builds (an element you add around <Calculator />). The result stub reads like a printed label: the giant magenta numeral, then
   "rolls to order", then the roll strip drawn as printed rolls (order = solid ink with a magenta core,
   have = outlined, partial = magenta-to-cyan conic split by --used).
5. "Reading your result" as a spec sheet: a definition list with dotted leader lines between term and value.
6. "The math, out in the open" on the full-width --plate band with white text, a halftone dot field fading from
   one corner, and the worked example in large type.
7. Footer as a print slug line: job name, date, colour bar, privacy link.

Motion (only inside prefers-reduced-motion: no-preference): one orchestrated load sequence. The colour bar
squares drop in with a stagger, the cyan and magenta headline ghosts slide from 14px apart into a 3px offset,
and the label strip unspools by scaling from the roll. Buttons press down 2px on :active. Nothing loops forever.

Mobile: one column. The roll illustration shrinks behind the headline, the ticket goes full width, the colour bar
stays, and nothing scrolls sideways."""

COOKBOOK = r"""TECHNIQUE COOKBOOK (adapt freely):
/* Off-register headline ghosts */
.headline{position:relative;color:var(--ink)}
.headline::before,.headline::after{content:attr(data-text);position:absolute;inset:0;z-index:-1}
.headline::before{color:var(--cyan);transform:translate(-3px,2px)}
.headline::after{color:var(--magenta);transform:translate(3px,-2px);mix-blend-mode:multiply}
/* (put the same text in data-text="...") */

/* Halftone dot field */
.halftone{background-image:radial-gradient(circle at center,rgba(255,255,255,.35) 1.4px,transparent 1.6px);
  background-size:9px 9px;-webkit-mask-image:linear-gradient(135deg,#000 0%,transparent 70%);
  mask-image:linear-gradient(135deg,#000 0%,transparent 70%)}

/* Paper grain from SVG noise */
body{background:var(--sheet) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .05 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}

/* Registration crosshair */
.reg{width:22px;height:22px;border-radius:50%;border:1.5px solid var(--ink);
  background:linear-gradient(var(--ink),var(--ink)) center/1.5px 100% no-repeat,
             linear-gradient(var(--ink),var(--ink)) center/100% 1.5px no-repeat}

/* Die-cut notched corners */
.ticket{--r:14px;mask:
  radial-gradient(circle var(--r) at 0 0,#0000 98%,#000) top left/51% 51% no-repeat,
  radial-gradient(circle var(--r) at 100% 0,#0000 98%,#000) top right/51% 51% no-repeat,
  radial-gradient(circle var(--r) at 0 100%,#0000 98%,#000) bottom left/51% 51% no-repeat,
  radial-gradient(circle var(--r) at 100% 100%,#0000 98%,#000) bottom right/51% 51% no-repeat}

/* Perforated tear line */
.perf{height:10px;background:radial-gradient(circle,var(--ink) 2px,transparent 2.5px) 0 50%/12px 10px repeat-x;opacity:.5}

/* Dotted leader lines in a definition list */
.spec div{display:flex;gap:.5rem;align-items:baseline}
.spec dt::after{content:"";flex:1;border-bottom:2px dotted var(--rule);margin-left:.5rem}
.spec dt{display:flex;flex:1}

/* Load sequence */
@media (prefers-reduced-motion:no-preference){
  .bar span{animation:drop .5s cubic-bezier(.2,.8,.2,1) both}
  .bar span:nth-child(2){animation-delay:.05s} /* and so on */
  @keyframes drop{from{transform:translateY(-120%)}}
  .headline::before{animation:regC .9s .2s cubic-bezier(.2,.8,.2,1) both}
  @keyframes regC{from{transform:translate(-14px,8px)}}
  .unspool{transform-origin:left center;animation:unspool 1.1s .4s cubic-bezier(.2,.8,.2,1) both}
  @keyframes unspool{from{transform:scaleX(0)}}
}"""

DIRECTED_BRIEF = f"""You are a senior front-end designer who executes art direction with precision and craft. Build this art
direction into the website, fully and boldly. The current design is clean but plain, and plain is a failure here.

Site: {SUBJECT}

{ART_DIRECTION}

{COOKBOOK}

Start by reading src/pages/index.astro, src/components/Calculator.astro, src/styles/site.css,
src/components/SiteHeader.astro and src/components/SiteFooter.astro. Then build the art direction.

{CONSTRAINTS}"""

BRIEFS = {"a": OPEN_BRIEF, "b": DIRECTED_BRIEF}
