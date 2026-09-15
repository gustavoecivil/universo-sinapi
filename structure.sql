-- Schema mínimo para carga opcional do Easy SINAPI ETL no PostgreSQL / Supabase.
-- Compatível com src/supabase.py e cleanup_reference.py (schema public por padrão).
--
-- Uso (psql / SQL Editor do Supabase):
--   \i structure.sql
--
-- Extensões: em projetos Supabase, unaccent e pg_trgm costumam estar disponíveis
-- no schema extensions; ajuste os nomes se necessário.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
  SELECT public.unaccent('public.unaccent'::regdictionary, $1)
$$;

CREATE OR REPLACE FUNCTION public.update_composicao_fts()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $$
BEGIN
  NEW.descricao_fts := to_tsvector('portuguese', unaccent(coalesce(NEW.descricao, '')));
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_insumo_fts()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $$
BEGIN
  NEW.descricao_fts := to_tsvector('portuguese', unaccent(coalesce(NEW.descricao, '')));
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.sinapi_referencias (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    referencia text NOT NULL,
    data_publicacao date,
    criada_em timestamptz DEFAULT now(),
    CONSTRAINT sinapi_referencias_pkey PRIMARY KEY (id),
    CONSTRAINT sinapi_referencias_referencia_key UNIQUE (referencia)
);

CREATE TABLE IF NOT EXISTS public.insumos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    codigo integer NOT NULL,
    descricao text NOT NULL,
    categoria text NOT NULL,
    unidade text NOT NULL,
    referencia_id uuid NOT NULL,
    descricao_fts tsvector,
    descricao_norm text GENERATED ALWAYS AS (public.immutable_unaccent(lower(descricao))) STORED,
    CONSTRAINT insumos_pkey PRIMARY KEY (id),
    CONSTRAINT insumos_referencia_id_fkey
        FOREIGN KEY (referencia_id) REFERENCES public.sinapi_referencias(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.insumo_custos (
    insumo_id uuid NOT NULL,
    uf character(2) NOT NULL,
    tipo_desoneracao text NOT NULL,
    custo numeric NOT NULL,
    CONSTRAINT insumo_custos_pkey PRIMARY KEY (insumo_id, uf, tipo_desoneracao),
    CONSTRAINT insumo_custos_tipo_desoneracao_check
        CHECK (tipo_desoneracao = ANY (ARRAY['COM'::text, 'SEM'::text])),
    CONSTRAINT insumo_custos_insumo_id_fkey
        FOREIGN KEY (insumo_id) REFERENCES public.insumos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.composicoes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    codigo integer NOT NULL,
    descricao text NOT NULL,
    categoria text NOT NULL,
    unidade text NOT NULL,
    referencia_id uuid NOT NULL,
    descricao_fts tsvector,
    descricao_norm text GENERATED ALWAYS AS (public.immutable_unaccent(lower(descricao))) STORED,
    CONSTRAINT composicoes_pkey PRIMARY KEY (id),
    CONSTRAINT composicoes_referencia_id_fkey
        FOREIGN KEY (referencia_id) REFERENCES public.sinapi_referencias(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.composicao_custos (
    composicao_id uuid NOT NULL,
    uf character(2) NOT NULL,
    tipo_desoneracao text NOT NULL,
    custo numeric NOT NULL,
    CONSTRAINT composicao_custos_pkey PRIMARY KEY (composicao_id, uf, tipo_desoneracao),
    CONSTRAINT composicao_custos_tipo_desoneracao_check
        CHECK (tipo_desoneracao = ANY (ARRAY['COM'::text, 'SEM'::text])),
    CONSTRAINT composicao_custos_composicao_id_fkey
        FOREIGN KEY (composicao_id) REFERENCES public.composicoes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.composicao_analitico (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    composicao_pai_id uuid NOT NULL,
    tipo_componente text NOT NULL,
    insumo_id uuid,
    composicao_filha_id uuid,
    coeficiente numeric NOT NULL,
    unidade text NOT NULL,
    CONSTRAINT composicao_analitico_pkey PRIMARY KEY (id),
    CONSTRAINT composicao_analitico_tipo_componente_check
        CHECK (tipo_componente = ANY (ARRAY['INSUMO'::text, 'COMPOSICAO'::text])),
    CONSTRAINT composicao_analitico_check CHECK (
        ((tipo_componente = 'INSUMO' AND insumo_id IS NOT NULL AND composicao_filha_id IS NULL)
         OR (tipo_componente = 'COMPOSICAO' AND composicao_filha_id IS NOT NULL AND insumo_id IS NULL))
    ),
    CONSTRAINT composicao_analitico_composicao_pai_id_fkey
        FOREIGN KEY (composicao_pai_id) REFERENCES public.composicoes(id) ON DELETE CASCADE,
    CONSTRAINT composicao_analitico_composicao_filha_id_fkey
        FOREIGN KEY (composicao_filha_id) REFERENCES public.composicoes(id) ON DELETE CASCADE,
    CONSTRAINT composicao_analitico_insumo_id_fkey
        FOREIGN KEY (insumo_id) REFERENCES public.insumos(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS insumos_codigo_referencia_idx
    ON public.insumos (codigo, referencia_id);

CREATE UNIQUE INDEX IF NOT EXISTS composicoes_codigo_referencia_idx
    ON public.composicoes (codigo, referencia_id);

CREATE INDEX IF NOT EXISTS idx_insumos_descricao_fts
    ON public.insumos USING gin (descricao_fts);

CREATE INDEX IF NOT EXISTS idx_composicoes_descricao_fts
    ON public.composicoes USING gin (descricao_fts);

CREATE INDEX IF NOT EXISTS idx_insumos_ref_descricao_norm_trgm
    ON public.insumos USING gin (referencia_id, descricao_norm gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_composicoes_ref_descricao_norm_trgm
    ON public.composicoes USING gin (referencia_id, descricao_norm gin_trgm_ops);

DROP TRIGGER IF EXISTS insumos_update_fts_trg ON public.insumos;
CREATE TRIGGER insumos_update_fts_trg
    BEFORE INSERT OR UPDATE ON public.insumos
    FOR EACH ROW EXECUTE FUNCTION public.update_insumo_fts();

DROP TRIGGER IF EXISTS composicoes_update_fts_trg ON public.composicoes;
CREATE TRIGGER composicoes_update_fts_trg
    BEFORE INSERT OR UPDATE ON public.composicoes
    FOR EACH ROW EXECUTE FUNCTION public.update_composicao_fts();

-- RLS: desativado por padrão para facilitar setup local.
-- Em produção no Supabase, habilite RLS e use SUPABASE_SERVICE_ROLE_KEY no ETL.
-- ALTER TABLE public.sinapi_referencias ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.insumos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.insumo_custos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.composicoes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.composicao_custos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.composicao_analitico ENABLE ROW LEVEL SECURITY;
