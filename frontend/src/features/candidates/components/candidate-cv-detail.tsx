import { InfoTooltip } from '@/common/components/info-tooltip';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import type { CandidateCvExtraction } from '@/features/candidates/types/candidate.types';

// Extracted verbatim from the post-upload result block on
// /candidates (candidates/page.tsx) -- shared with the new
// /candidates/[candidateId] detail page, same JSX either way.
export function CandidateCvDetail({ cv }: { cv: CandidateCvExtraction }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{cv.full_name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="flex items-center gap-1">
          <span>Total years of experience: {cv.total_years_experience}</span>
          <InfoTooltip text="Computed from the extracted experience entries' start and end dates — not a value stored on the CV itself." />
        </p>

        <div>
          <h3 className="font-heading text-sm text-muted-foreground">Education</h3>
          <ul className="list-inside list-disc">
            {cv.education.map((edu) => (
              <li key={edu.source_span}>
                {edu.degree}
                {edu.field && ` in ${edu.field}`} — {edu.institution}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-heading text-sm text-muted-foreground">Experience</h3>
          <ul className="list-inside list-disc">
            {cv.experience.map((exp) => (
              <li key={exp.source_span}>
                {exp.title} — {exp.employer} ({exp.start_date} to {exp.end_date ?? 'present'})
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-heading text-sm text-muted-foreground">Certifications</h3>
          {cv.certifications.length > 0 ? (
            <ul className="list-inside list-disc">
              {cv.certifications.map((cert) => (
                <li key={cert.source_span}>
                  {cert.name}
                  {cert.issuing_body && ` — ${cert.issuing_body}`}
                  {cert.expiry_date && ` (expires ${cert.expiry_date})`}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">None listed.</p>
          )}
        </div>

        <div>
          <h3 className="font-heading text-sm text-muted-foreground">Languages</h3>
          {cv.languages.length > 0 ? (
            <p>{cv.languages.map((lang) => `${lang.language} (${lang.level})`).join(', ')}</p>
          ) : (
            <p className="text-sm text-muted-foreground">None listed.</p>
          )}
        </div>

        <div>
          <h3 className="font-heading text-sm text-muted-foreground">Skills</h3>
          <p>{cv.raw_skills.join(', ')}</p>
        </div>

        <details>
          <summary className="cursor-pointer text-muted-foreground">Raw JSON</summary>
          <pre className="overflow-x-auto text-xs">{JSON.stringify(cv, null, 2)}</pre>
        </details>
      </CardContent>
    </Card>
  );
}
