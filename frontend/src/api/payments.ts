import { apiRequest } from './fetch';
import type { CreditProductListResponse } from './types';

export interface CheckoutSessionRequest {
  product_id: string;
  quantity?: number;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
}

export const paymentsApi = {
  listProducts: () =>
    apiRequest<CreditProductListResponse>('GET', '/payments/products'),
  createCheckoutSession: (body: CheckoutSessionRequest) =>
    apiRequest<CheckoutSessionResponse>('POST', '/payments/checkout', { body }),
};
