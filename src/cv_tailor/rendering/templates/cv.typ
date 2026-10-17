#let cv = json(bytes(sys.inputs.cv))
#let accent = rgb("#2A7B88")
#let rule-color = rgb("#39A5B7")
#let ink = rgb("#404040")
#let dark = rgb("#262626")

#let body-size = 11.04pt
#let line-gap = 4.47pt

#set document(title: cv.contact.name + " CV", author: cv.contact.name)
#set page(
  paper: "us-letter",
  margin: (left: 57.6pt, right: 57.6pt, top: 50.4pt, bottom: 57.6pt),
  foreground: context {
    if counter(page).get().first() > 1 {
      place(
        bottom + right,
        dx: -57.6pt,
        dy: -7.3pt,
        text(fill: accent)[Page #counter(page).display()],
      )
    }
  },
)
#set text(
  font: ((name: "Libertinus Serif", covers: regex("&")), "Caladea", "Libertinus Serif"),
  size: body-size,
  fill: ink,
  lang: "en",
  top-edge: 0.8em,
  bottom-edge: -0.2em,
)
#set par(justify: false, leading: 1.91pt, spacing: 0pt)
#set block(spacing: 0pt)
#set list(
  marker: [#box(width: 11.3pt, align(left)[·])],
  indent: 0pt,
  body-indent: 0pt,
  spacing: 4.46pt,
)
#show list: set par(leading: 4.46pt)
#show link: set text(fill: accent)
#show link: underline

#show heading.where(level: 1): it => block(above: 20.76pt, below: 6.86pt, sticky: true)[
  #text(size: 14.04pt, weight: "bold", fill: accent)[#it.body]
]

#let span(start, end) = if end == "" or end == start { start } else { start + " – " + end }

#let link_label(address) = if address.contains("linkedin") {
  "LinkedIn"
} else if address.contains("github") {
  "GitHub"
} else {
  "Portfolio"
}

#let stacked(items) = for (index, item) in items.enumerate() {
  if index > 0 { v(line-gap) }
  par(item)
}

#let entry(title, details, bullets, spaced) = {
  if spaced { v(16.4pt, weak: true) }
  block(sticky: true)[
    #text(size: 12pt, weight: "bold", fill: dark)[#upper(title)]
    #v(4.73pt)
    #text(size: 9.96pt, style: "italic", fill: dark)[#upper(details)]
    #v(4.08pt)
  ]
  if bullets.len() > 0 {
    list(..bullets.map(bullet => [#bullet]))
  }
}

#let experience_entry(item, spaced) = {
  if item.location == "" {
    entry(item.role, item.company + " | " + span(item.start, item.end), item.bullets, spaced)
  } else {
    entry(
      item.company + " | " + item.role,
      item.location + " | " + span(item.start, item.end),
      item.bullets,
      spaced,
    )
  }
}

#v(4.2pt)
#pad(left: 5.5pt, text(size: 27.96pt, fill: accent)[#cv.contact.name])
#v(6.7pt)
#rect(width: 100%, height: 1.25pt, fill: rule-color, stroke: none)
#v(2.05pt)
#if cv.contact.headline != "" [
  #cv.contact.headline
]

= Contact Information
#stacked((
  "Phone: " + cv.contact.phone,
  "Email: " + cv.contact.email,
  "Location: " + cv.contact.location,
  ..cv.contact.links.map(address => link_label(address) + ": " + link("https://" + address, address)),
))

= Summary
#cv.summary

#if cv.skills.len() > 0 [
  = Skills
  #stacked(cv.skills.map(group => group.group + ": " + group.items.join(", ")))
]

= Experience
#for (index, item) in cv.experience.enumerate() {
  experience_entry(item, index > 0)
}

#if cv.internships.len() > 0 [
  = INTERNSHIPS
  #for (index, item) in cv.internships.enumerate() {
    experience_entry(item, index > 0)
  }
]

#if cv.projects.len() > 0 [
  = Projects
  #for (index, project) in cv.projects.enumerate() {
    let details = if project.link != none { (project.link,) } else { () }
    let tech = if project.tech.len() > 0 { (project.tech.join(", "),) } else { () }
    entry(project.name, (..details, ..tech).join(" | "), project.bullets, index > 0)
  }
]

#if cv.education.len() > 0 [
  = Education
  #for (index, item) in cv.education.enumerate() {
    entry(item.institution, item.degree + " | " + span(item.start, item.end), item.bullets, index > 0)
  }
]

#if cv.certifications.len() > 0 [
  = Certifications
  #list(..cv.certifications.map(certification => [#certification]))
]

#if cv.languages.len() > 0 [
  = LANGUAGES
  #stacked(cv.languages)
]
