export interface ProblemDetails {
  type: string
  title: string
  status: number
  detail: string
  request_id?: string
  errors?: Array<{
    field?: string
    code?: string
    message?: string
  }>
}

export interface ApiError extends Error {
  status: number
  details: ProblemDetails | null
}
