"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAppPreferences } from "../components/app-providers";
import { api, invalidateProject, keys } from "./api";

/* Reads. Text-bearing endpoints key on locale so switching language refetches localized text. */

export function useDashboard(projectId: string, releaseId: string) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.dashboard(projectId, releaseId, locale),
    queryFn: () => api.dashboard(projectId, releaseId, locale),
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === projectId ? previous : undefined,
    refetchOnWindowFocus: "always",
  });
}

export function useRequirements(projectId: string) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.requirements(projectId, locale),
    queryFn: () => api.requirements(projectId, locale),
  });
}

export function useRequirement(projectId: string, humanId: string | null) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.requirement(projectId, humanId || "", locale),
    queryFn: () => api.requirement(projectId, humanId || "", locale),
    enabled: Boolean(humanId),
  });
}

export function useChanges(projectId: string, enabled = true) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.changes(projectId, locale),
    queryFn: () => api.changes(projectId, locale),
    enabled,
  });
}

export function useEvidence(projectId: string, enabled = true) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.evidence(projectId, locale),
    queryFn: () => api.evidence(projectId, locale),
    enabled,
  });
}

export function useAttention(projectId: string) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.attention(projectId, locale),
    queryFn: () => api.attention(projectId, locale),
    refetchOnWindowFocus: "always",
  });
}

export function useActivity(projectId: string, enabled = true) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.activity(projectId, locale),
    queryFn: () => api.activity(projectId, locale, 20),
    enabled,
  });
}

export function useReadiness(projectId: string, enabled = true) {
  return useQuery({
    queryKey: keys.readiness(projectId),
    queryFn: () => api.readiness(projectId),
    enabled,
  });
}

export function useProposals(projectId: string) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.proposals(projectId, locale),
    queryFn: () => api.proposals(projectId, locale, "draft"),
    refetchOnWindowFocus: "always",
  });
}

export function useScopeVersions(projectId: string, enabled = true) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.scopeVersions(projectId, locale),
    queryFn: () => api.scopeVersions(projectId, locale),
    enabled,
  });
}

export function useTeam(projectId: string) {
  return useQuery({ queryKey: keys.team(projectId), queryFn: () => api.team(projectId) });
}

export function useProjects() {
  const { locale } = useAppPreferences();
  return useQuery({ queryKey: keys.projects(locale), queryFn: () => api.projects(locale) });
}

export function useReleases(projectId: string, enabled = true) {
  const { locale } = useAppPreferences();
  return useQuery({
    queryKey: keys.releases(projectId, locale),
    queryFn: () => api.releases(projectId, locale),
    enabled,
  });
}

export function useAgents(enabled = true) {
  return useQuery({ queryKey: keys.agents(), queryFn: api.agents, enabled, staleTime: 5 * 60_000 });
}

export function useAgentRuns(projectId: string, enabled = true) {
  return useQuery({
    queryKey: keys.agentRuns(projectId),
    queryFn: () => api.agentRuns(projectId),
    enabled,
  });
}

/**
 * Every write goes through here: on success the whole project is invalidated, and the mutation
 * stays pending until the refetch lands, so buttons keep their busy state until the views agree.
 */
export function useProjectMutation<TResult, TVariables = void>(
  projectId: string,
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => invalidateProject(queryClient, projectId),
  });
}
