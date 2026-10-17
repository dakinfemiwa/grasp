# Task: Evolve the existing Flexa MVP into Grasp

You are working in an existing codebase for an adaptive learning platform. Your task is to adapt the existing MVP into **Grasp**, an adaptive learning platform initially focused on A-level Edexcel Mathematics, beginning with Pure Mathematics modelling questions (excluding calculus for now).

Do not blindly rebuild the project. First inspect the repository, understand its architecture and existing functionality, identify reusable components, and then implement a focused, maintainable MVP that builds on what is already there.

## 1. Product rename: Flexa → Grasp

Change the product name from **Flexa** to **Grasp** throughout the application.

Inspect and update, where applicable:

- Application titles, metadata, page headings and visible branding.
- Navigation, onboarding, dashboards and user-facing copy.
- README and project documentation.
- Package metadata and internal configuration where appropriate.
- Tests, fixtures and seed data.
- Any references to Flexa in source code, comments or configuration where the name represents the product.

Use `Grasp` as the display name and `grasp` where a lowercase identifier is appropriate.

Do not perform unsafe, indiscriminate global replacements. Preserve third-party names, unrelated identifiers and historical references where changing them would be incorrect.

**Repository rename:** The remote Git repository may still be named Flexa. Do not assume you can rename it locally or remotely. Inspect the Git remote and repository configuration, explain whether a rename is needed, and provide the exact manual steps if remote renaming requires an external action. Do not change the remote URL speculatively.

## 2. Inspect the current MVP before changing it

Start by examining:

- Frameworks, dependencies and project structure.
- Existing pages, components, routes and data models.
- Authentication and user/student relationships.
- Database schema, queries, mutations and seed data.
- Existing learning objectives, goals, subgoals, tasks or other learning structures.
- Tests, scripts, development instructions and deployment configuration.
- Any existing question-generation, tutoring or assessment functionality.

Write a short implementation plan based on what actually exists.

Preserve working functionality unless there is a concrete reason to change it. Reuse existing architectural patterns and dependencies where sensible. Avoid introducing a new framework, database, service or abstraction without a clear need.

Then implement the changes rather than stopping after producing the plan.

## 3. Initial product scope

Grasp's first learning domain is:

**A-level Edexcel Mathematics → Pure Mathematics → Mathematical modelling, excluding calculus.**

The initial scope includes:

- Linear modelling.
- Quadratic modelling.
- Trigonometric modelling.
- Interpreting and evaluating mathematical models.

Do not implement calculus-based optimisation, differentiation or integration questions as part of this initial modelling question bank. Do not confuse this restriction with a claim that calculus is excluded from the overall A-level qualification.

Use the Edexcel A-level Mathematics specification as the initial curriculum reference. Relevant official sources include:

- https://qualifications.pearson.com/en/qualifications/edexcel-a-levels/mathematics-2017.html
- https://qualifications.pearson.com/en/qualifications/edexcel-a-levels/mathematics-2017.html

If the repository already contains curriculum data, inspect and adapt it rather than duplicating it. Do not claim complete specification coverage unless it has been verified.

## 4. Introduce an explicit modelling objective catalogue

Represent modelling skills as observable student capabilities, not merely topic labels.

Create a versioned, maintainable catalogue containing at least these proposed objectives:

| ID     | Objective                           | Intended evidence                                                   |
| ------ | ----------------------------------- | ------------------------------------------------------------------- |
| MOD-01 | Extract relevant information        | Identifies quantities, units and conditions                         |
| MOD-02 | Define variables                    | Defines quantities clearly and consistently                         |
| MOD-03 | Identify mathematical relationships | Selects relationships supported by the problem                      |
| MOD-04 | Make assumptions                    | Identifies or states reasonable simplifications                     |
| MOD-05 | Construct a mathematical model      | Forms equations or functions representing a situation               |
| MOD-06 | Select a solution method            | Chooses an appropriate mathematical approach                        |
| MOD-07 | Solve the model                     | Obtains a mathematically valid solution                             |
| MOD-08 | Interpret results                   | Explains results in the original context                            |
| MOD-09 | Validate a result                   | Checks units, constraints and consistency                           |
| MOD-10 | Evaluate a model                    | Identifies limitations and potential refinements                    |
| MOD-11 | Transfer modelling skills           | Applies the underlying reasoning in a new context or representation |

These are Grasp's proposed internal IDs, not official Edexcel identifiers.

For each objective, support:

- A stable ID and title.
- A clear description.
- Observable success criteria.
- Relevant prerequisites, where justified.
- Applicable mathematical domains or template references.
- The type of evidence that could demonstrate the skill.

Represent prerequisite relationships explicitly and allow multiple prerequisites. Do not force the objectives into an artificial linear sequence.

Keep the objective catalogue separate from individual questions, question templates, scenarios and student evidence.

If the current application has a suitable goal/subgoal/task structure, adapt or map it to this model instead of automatically replacing it.

## 5. Separate the core data concepts

Design or adapt the existing data model to distinguish the following concepts.

### A. Learning objective

The capability a question is intended to assess.

### B. Mathematical question template

A reusable mathematical structure specifying:

- Template ID and immutable version.
- Mathematical domain.
- Primary objective and any secondary objectives.
- Parameter definitions and valid ranges.
- Executable constraints.
- Prompt-generation rules.
- Solution logic.
- Answer specification.
- Marking criteria.
- Difficulty characteristics.
- Validation requirements.
- Review status.

### C. Scenario definition

A reusable context or representation, where appropriate, specifying:

- Scenario ID and version.
- Description and relevant entities.
- Mathematical relationships represented.
- Compatible templates.
- Assumptions and constraints.
- Permitted presentation formats.
- Review status.

### D. Generated question instance

A concrete question produced from a template and optional scenario, containing:

- Unique instance ID.
- Template ID and version.
- Parameter values and random seed.
- Rendered question.
- Expected answer and worked solution.
- Objective tags.
- Validation results.
- Scenario reference, if applicable.

### E. Student evidence

A record of an attempt, including:

- Student and question references.
- Submitted answer or structured working.
- Marking outcome.
- Objective-level evidence.
- Hints or scaffolding used.
- Timestamp and attempt number.

Adapt these concepts to the existing database and authentication architecture. Do not create unnecessary tables or duplicate existing concepts. Document significant schema changes and migrations.

Avoid using `unknown` for all answer payloads or storing executable JavaScript in database strings. Use typed structures and executable validators in application code, with runtime validation at external data boundaries.

## 6. Build an initial question-generation engine

Implement the smallest useful end-to-end engine rather than an extensive framework.

Start with one fully working template: **quadratic model construction from rectangular dimensions**.

Example question:

"A rectangular garden has a length 4 metres greater than its width. Its area is 96 square metres. Form an equation that can be used to find its dimensions, and determine the dimensions."

Expected modelling:

- Define the width as \(x\).
- Express the length as \(x+4\).
- Construct \(x(x+4)=96\).
- Solve the resulting equation.
- Reject the negative width.
- Interpret the dimensions as 8 m by 12 m.
- Verify the result against the original conditions.

The implementation should support:

- Typed parameter specifications.
- Valid parameter generation.
- Explicit mathematical constraints.
- Deterministic generation from a seed and template version.
- Prompt rendering.
- Answer calculation.
- A worked solution.
- Structured marking for the key modelling steps.
- Validation that checks the result against the original conditions.
- Clear errors when parameters or generated instances are invalid.

Generate variations by selecting valid values and deriving dependent parameters where useful. Do not simply randomise numbers independently and hope the resulting question has a clean solution.

For example, choose positive integer width \(x\) and positive difference \(d\), then derive the area \(A=x(x+d)\). This guarantees a known positive integer solution for this template, provided the implementation also enforces sensible ranges.

Do not make the entire engine dependent on an LLM. Use deterministic TypeScript for parameter generation, constraints, calculations and objective-level marking. AI may assist with offline authoring or future explanation features, but should not be required to produce a valid question at runtime.

## 7. Prepare the next template families without overbuilding

After the quadratic template works, define a clean extension point for:

1. Linear modelling.
2. Trigonometric modelling.

Do not implement complex general-purpose symbolic mathematics unless the existing project already has suitable support.

For trigonometric modelling, use geometrically valid scenarios and explicit assumptions. For example, a right-triangle height-and-distance problem may use a tangent relationship, while a ramp may use sine or cosine depending on which sides and angle are specified.

Do not treat all scenarios as interchangeable wrappers around equations. A scenario must be compatible with the mathematical template and should not accidentally reveal the reasoning the student is meant to demonstrate.

Model interpretation and evaluation should eventually have templates that present a supplied model and ask the student to interpret its parameters, test its validity, or critique its assumptions.

## 8. Implement a small, controlled scenario library

Create a modest initial collection of reviewed scenario definitions rather than a combinatorial generator.

Potential contexts include:

- Garden dimensions.
- Sports-ground layouts.
- Workshop dimensions.
- Ramps and accessible paths.
- Surveying and height measurements.
- Rectangular event layouts.

Only include scenarios for which the required information and mathematical relationships are fully specified.

Represent scenario-template compatibility explicitly. Do not randomly combine actors, objects, settings and relationships if the resulting situation would be implausible or mathematically inconsistent.

Questions do not always need a narrative. For some modelling objectives, a diagram, table, graph or abstract mathematical representation is more appropriate.

Clearly distinguish draft scenarios from reviewed and approved scenarios. Only approved content should enter the normal student question bank.

## 9. Validation and quality controls

Build validation into the generation workflow.

At minimum, check:

**Structural validity**

- Referenced objectives, templates and scenarios exist.
- Template and scenario compatibility is satisfied.
- Required parameters are present and correctly typed.

**Mathematical validity**

- Parameter constraints hold.
- Units are consistent.
- A valid solution exists where required.
- The computed answer satisfies the original conditions.
- Invalid or extraneous solutions are handled appropriately.

**Pedagogical validity**

- The primary objective matches the capability actually assessed.
- The prompt does not give away the intended reasoning unintentionally.
- The expected answer and marking criteria are aligned.

**Presentation validity**

- The question is clear and contains sufficient information.
- There is no unintended ambiguity.
- Relevant assumptions and units are communicated.

Automate structural and mathematical checks where possible. Use tests and a review status for pedagogical quality; do not pretend that passing mathematical tests alone establishes educational quality.

Do not make an LLM the sole validator.

## 10. Student adaptation: prepare the data, avoid unsupported diagnosis

Connect generated questions to the existing student model if the current architecture supports it.

Record objective-level evidence rather than storing only an overall topic score. A student who can solve a quadratic equation may still struggle to construct one from a word problem.

For the initial version:

- Record attempts and marking outcomes.
- Preserve which objectives each question assesses.
- Record hints and scaffolding where available.
- Keep evidence distinguishable from the student's estimated mastery.
- Avoid declaring a prerequisite weakness from one incorrect answer.
- Do not implement an elaborate Bayesian or machine-learning mastery model unless the existing MVP already has one and it is appropriate.

A simple, transparent baseline is sufficient initially. The architecture should permit future refinement.

## 11. User experience

Integrate the functionality into the existing application rather than creating an isolated demo unless that is genuinely the best fit.

The student should be able to:

1. Open a modelling practice area.
2. See a question with clear mathematical notation and units.
3. Submit an answer.
4. Receive appropriate marking or feedback.
5. Review the worked solution.
6. Have the attempt recorded against the relevant objectives.
7. Attempt a valid variation.

Prioritise correctness, clarity and a functional end-to-end experience over visual polish. Reuse existing UI components and styles.

If free-form working cannot be marked reliably, start with a structured response format that captures variables, equation construction and final answer separately. Do not claim to assess reasoning that the implementation does not actually inspect.

## 12. Testing and acceptance criteria

Add or update tests for the new behaviour.

The work is complete when:

- The application consistently presents itself as Grasp.
- Existing core MVP functionality still works.
- The modelling objective catalogue is represented in code or the existing data layer.
- The quadratic template generates valid, reproducible questions.
- At least 20 generated instances pass automated structural and mathematical validation across a sensible range of parameters.
- Each instance has a correct expected answer and worked solution.
- Invalid parameters are rejected.
- The negative quadratic root is not accepted as a physical width.
- The marking process distinguishes equation construction, solving and contextual interpretation where supported.
- Question attempts can be associated with the objectives they assess.
- The relevant tests pass.
- The README explains the architecture, how to run tests, how to generate questions, and how to add a template.
- Any incomplete features, migrations or manual repository-renaming steps are documented honestly.

Do not satisfy the 20-instance criterion by writing 20 hard-coded copies. Generate them through the same reusable engine.

## 13. Working method and final report

Work in this order:

1. Inspect the repository and current behaviour.
2. Produce a concise plan based on the actual code.
3. Implement the product rename and objective catalogue.
4. Implement the quadratic question template and generation pipeline.
5. Integrate the question flow into the application.
6. Add tests and run the relevant checks.
7. Update documentation.

Keep changes incremental and consistent with the repository's conventions. Do not delete existing data or make destructive schema changes without a safe migration strategy.

At the end, report:

- What you inspected.
- What you changed.
- The main architectural decisions.
- The files and database/schema changes involved.
- Tests run and their actual results.
- Any remaining limitations.
- Exact manual steps for renaming the remote Git repository, if necessary.
- The recommended next implementation step.

**Priorities:** correctness first, preserve existing functionality second, maintainability third, polish fourth. Build a small, working foundation that Grasp can grow from rather than an overengineered system.
