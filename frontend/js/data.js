// Static data. Edit lists here; no other file needs to change.
export const GRADE_LEVELS = ['Kindergarten','Grade 1 (MATATAG)','Grade 2','Grade 3','Grade 4 (MATATAG)','Grade 5','Grade 6','Grade 7 (MATATAG)','Grade 8','Grade 9','Grade 10 (MATATAG)','Grade 11 (SHS)','Grade 12 (SHS)'];

export const SUBJECT_AREAS = ['Makabansa','Language / Wikang Filipino','Reading & Literacy','Mathematics','Science / Agham','Araling Panlipunan','GMRC / Values Education','English','Filipino','MAPEH','EPP / TLE','General Senior High Subject'];

export const SAMPLE_PROMPTS = [
  { label: 'Grade 1 Makabansa: Pagkilala sa Sarili at Pamilya', gradeLevel: 'Grade 1 (MATATAG)', subjectArea: 'Makabansa', quarter: 'Term 1', weekNumber: 'Week 2',
    topic: 'Nauunawaan ang sariling pagkakakilanlan (pangalan, edad, tirahan, at pamilya) at ang kahalagahan ng paggalang sa kapwa bata.' },
  { label: 'Grade 4 Science: Physical & Chemical Changes in Matter', gradeLevel: 'Grade 4 (MATATAG)', subjectArea: 'Science / Agham', quarter: 'Term 1', weekNumber: 'Week 3',
    topic: 'Physical & Chemical Changes in Matter' },
  { label: 'Grade 7 English: Analyzing Local Folktales & Taglish Expressions', gradeLevel: 'Grade 7 (MATATAG)', subjectArea: 'English', quarter: 'Term 2', weekNumber: 'Week 1',
    topic: 'Analyzing Local Folktales & Taglish Expressions' },
  { label: 'Grade 10 Math: Polynomial Functions in Community Problem Solving', gradeLevel: 'Grade 10 (MATATAG)', subjectArea: 'Mathematics', quarter: 'Term 1', weekNumber: 'Week 4',
    topic: 'Polynomial Functions in Community Problem Solving' },
];

// Procedure labels (a–i) in DLL order. Keys must match the backend JSON.
export const PROCEDURES = [
  ['a_review','Panimula / Balik-Aral'], ['b_purpose','Pagganyak / Layunin ng Aralin'],
  ['c_examples','Paglalahad ng mga Halimbawa'], ['d_discussion','Pagtatalakay ng Bagong Konsepto'],
  ['e_mastery','Paglinang sa Kabihasnan (Formative Assessment)'], ['f_application','Paglalapat ng Aralin sa Araw-araw na Buhay'],
  ['g_generalization','Paglalahat ng Aralin'], ['h_evaluation','Pagtataya ng Natutuhan'], ['i_remediation','Karagdagang Gawain / Remediation'],
];

export const REFLECTION = [
  ['learners80Percent','Bilang ng mag-aaral na nakakuha ng 80%'], ['learnersNeedingRemediation','Mag-aaral na nangangailangan ng remediation'],
  ['remediationEffective','Naging epektibo ba ang remediation?'], ['learnersContinuingRemediation','Mag-aaral na magpapatuloy sa remediation'],
  ['effectiveTeachingStrategies','Mabisang estratehiya sa pagtuturo'], ['difficultiesEncountered','Suliraning naranasan'], ['innovationsUsed','Inobasyon na ginamit'],
];

// Shown on first load so the page is never empty. Same shape as the backend response.
export const SAMPLE_DLL = {
  id: 'sample', title: 'Sample: Grade 1 Makabansa', dateCreated: '2026-01-01', providerUsed: 'auto',
  header: { schoolName: 'Sample School', teacherName: 'Sample Teacher', teachingDates: 'August 3 - 7, 2026', gradeLevel: 'Grade 1 (MATATAG)', learningArea: 'Makabansa', quarter: 'Term 1', weekNumber: 'Week 2', division: '', region: '', noOfSessions: '4 Sessions', references: '', declarationOfAiUse: '' },
  objectives: { contentStandard: 'Sample content standard.', performanceStandard: 'Sample performance standard.', learningCompetencies: ['Nakikilala ang sarili at pamilya.'] },
  content: { topic: 'Pagkilala sa Sarili at Pamilya', subtopic: '', integrationValues: 'Paggalang', hotsSkills: 'Pagsusuri' },
  resources: { teacherGuidePages: '', learnerMaterialPages: '', textbookPages: '', additionalMaterials: '' },
  procedures: { a_review: 'Sample.', b_purpose: '', c_examples: '', d_discussion: '', e_mastery: '', f_application: '', g_generalization: '', h_evaluation: '', i_remediation: '' },
  remarks: { notes: '' },
  reflection: { learners80Percent: '', learnersNeedingRemediation: '', remediationEffective: '', learnersContinuingRemediation: '', effectiveTeachingStrategies: '', difficultiesEncountered: '', innovationsUsed: '' },
};
