-- med_roster schema
-- Run this in pgAdmin's Query Tool against the `med_roster` database.
-- Drops and recreates all tables — safe only because current data is test/empty.

BEGIN;

DROP TABLE IF EXISTS public.assignment CASCADE;
DROP TABLE IF EXISTS public.request CASCADE;
DROP TABLE IF EXISTS public.demand_template_skill_requirement CASCADE;
DROP TABLE IF EXISTS public.demand_template CASCADE;
DROP TABLE IF EXISTS public.roster_period CASCADE;
DROP TABLE IF EXISTS public.staff_skill CASCADE;
DROP TABLE IF EXISTS public.staff CASCADE;
DROP TABLE IF EXISTS public.ward CASCADE;

-- Staff: one row per person. Surrogate key instead of `name`, since names
-- can collide between two people and can change for one person.
CREATE TABLE public.staff (
    staff_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name character varying(60) NOT NULL,
    employment_fraction real,
    classification character varying(20)
);

-- A staff member can hold multiple skills/certifications, so this is a
-- separate one-to-many table rather than a single column on staff.
CREATE TABLE public.staff_skill (
    staff_id integer NOT NULL REFERENCES public.staff(staff_id) ON DELETE CASCADE,
    skill character varying(20) NOT NULL,
    PRIMARY KEY (staff_id, skill)
);

CREATE TABLE public.ward (
    ward_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ward_name character varying(25) NOT NULL UNIQUE,
    shift_structure text
);

-- Each staffing requirement now belongs to a specific ward.
CREATE TABLE public.demand_template (
    demand_template_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ward_id integer NOT NULL REFERENCES public.ward(ward_id) ON DELETE CASCADE,
    day character varying(10),
    shift character varying(10),
    minimum_staff_count integer
);

-- Skill mix needs multiple simultaneous minimums per shift (e.g. >=3 RN AND
-- >=1 in-charge), so it's a separate one-to-many table rather than a single
-- integer column.
CREATE TABLE public.demand_template_skill_requirement (
    demand_template_id integer NOT NULL REFERENCES public.demand_template(demand_template_id) ON DELETE CASCADE,
    classification character varying(20) NOT NULL,
    minimum_count integer NOT NULL,
    PRIMARY KEY (demand_template_id, classification)
);

-- The fortnight/month being generated, now tied to the ward it's for.
CREATE TABLE public.roster_period (
    roster_period_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ward_id integer NOT NULL REFERENCES public.ward(ward_id) ON DELETE CASCADE,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status character varying(10) NOT NULL DEFAULT 'draft'
);

CREATE TABLE public.request (
    request_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staff_id integer NOT NULL REFERENCES public.staff(staff_id) ON DELETE CASCADE,
    date date,
    request_type text,
    approved boolean
);

-- The solver's output: (staff, date, shift) triples, now linked to the
-- roster period they belong to, with a flag distinguishing solver output
-- from hand edits, and a uniqueness guard against double-booking a staff
-- member on the same day.
CREATE TABLE public.assignment (
    assignment_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staff_id integer NOT NULL REFERENCES public.staff(staff_id) ON DELETE CASCADE,
    roster_period_id integer NOT NULL REFERENCES public.roster_period(roster_period_id) ON DELETE CASCADE,
    date date NOT NULL,
    shift text NOT NULL,
    source character varying(10) NOT NULL DEFAULT 'solver' CHECK (source IN ('solver', 'manual')),
    UNIQUE (staff_id, date)
);

COMMIT;
