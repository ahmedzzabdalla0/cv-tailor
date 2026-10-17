#let cv = json(bytes(sys.inputs.cv))

#set document(title: cv.contact.name + " CV", author: cv.contact.name)
#set page(paper: "a4", margin: (x: 1.6cm, y: 1.4cm))
#set text(font: ("Libertinus Serif", "New Computer Modern"), size: 10pt, lang: "en")
#set par(justify: false, leading: 0.5em, spacing: 0.55em)
#set list(indent: 0.2em, body-indent: 0.5em, spacing: 0.35em)
#set block(spacing: 0.6em)

#show heading.where(level: 1): it => block(above: 0.8em, below: 0.45em, sticky: true)[
  #text(size: 10.5pt, weight: "bold", tracking: 0.06em)[#upper(it.body)]
  #v(-0.5em)
  #line(length: 100%, stroke: 0.5pt)
]

#let dated_line(title, dates) = {
  strong(title)
  h(1fr)
  dates
}

#align(center)[
  #text(size: 20pt, weight: "bold")[#cv.contact.name]

  #(cv.contact.location, cv.contact.phone, cv.contact.email, ..cv.contact.links).join(" | ")
]

= Summary
#cv.summary

#if cv.skills.len() > 0 [
  = Skills
  #for group in cv.skills {
    par(strong(group.group + ": ") + group.items.join(", "))
  }
]

= Experience
#for entry in cv.experience {
  block({
    dated_line(entry.role + ", " + entry.company, entry.start + " – " + entry.end)
    linebreak()
    emph(entry.location)
    list(..entry.bullets.map(bullet => [#bullet]))
  })
}

#if cv.projects.len() > 0 [
  = Projects
  #for project in cv.projects {
    block({
      dated_line(project.name, if project.link != none { project.link } else { "" })
      if project.tech.len() > 0 {
        linebreak()
        emph(project.tech.join(", "))
      }
      list(..project.bullets.map(bullet => [#bullet]))
    })
  }
]

#if cv.education.len() > 0 [
  = Education
  #for entry in cv.education {
    par(dated_line(entry.degree + ", " + entry.institution, entry.start + " – " + entry.end))
  }
]

#if cv.certifications.len() > 0 [
  = Certifications
  #list(..cv.certifications.map(certification => [#certification]))
]
