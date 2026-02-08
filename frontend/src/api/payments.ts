import apiClient from './client';
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
  listProducts: async () => {
    const response = await apiClient.get<CreditProductListResponse>(
      '/payments/products'
    );
    return response.data;
  },
  createCheckoutSession: async (payload: CheckoutSessionRequest) => {
    const response = await apiClient.post<CheckoutSessionResponse>(
      '/payments/checkout',
      payload
    );
    return response.data;
  },
};
