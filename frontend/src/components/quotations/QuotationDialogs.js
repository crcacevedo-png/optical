/**
 * Dialogos extraidos de QuotationsPage.js:
 * - QuotationDetailDialog: vista de detalle + acciones (aceptar/rechazar/convertir/PDF).
 * - ConvertToSaleDialog: conversion de cotizacion a venta con metodo de pago.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { CheckCircle, XCircle, Download, ShoppingCart } from 'lucide-react';

export function QuotationDetailDialog({
  open, onOpenChange, quotation, statusConfig,
  onDownloadPdf, onStatusChange, onOpenConvert, formatCurrency,
}) {
  if (!quotation) return null;
  const sc = statusConfig[quotation.status] || statusConfig.pendiente;
  const StatusIcon = sc.icon;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="text-xl">Cotizacion {quotation.quotation_number}</DialogTitle>
            <span className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium ${sc.color}`}>
              <StatusIcon className="w-4 h-4" /> {sc.label}
            </span>
          </div>
        </DialogHeader>

        <div className="space-y-5">
          <div className="bg-slate-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-500">Paciente:</span> <span className="font-medium">{quotation.patient_name}</span></div>
              <div><span className="text-slate-500">Telefono:</span> {quotation.patient_phone}</div>
              <div><span className="text-slate-500">Fecha:</span> {quotation.created_at?.slice(0, 10)}</div>
              <div><span className="text-slate-500">Vigencia hasta:</span> {quotation.expiry_date}</div>
            </div>
          </div>

          <div>
            <Label className="font-semibold mb-2 block">Productos</Label>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Producto</TableHead>
                    <TableHead className="text-center">Cant</TableHead>
                    <TableHead className="text-right">P. Unit.</TableHead>
                    <TableHead className="text-right">Subtotal</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(quotation.items || []).map((item, idx) => (
                    <TableRow key={item.product_id || `item-${idx}`}>
                      <TableCell className="font-medium text-sm">{item.name}</TableCell>
                      <TableCell className="text-center">{item.quantity}</TableCell>
                      <TableCell className="text-right">{formatCurrency(item.unit_price)}</TableCell>
                      <TableCell className="text-right font-medium">{formatCurrency(item.subtotal)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="flex justify-end">
            <div className="w-64 space-y-1.5">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Subtotal:</span>
                <span>{formatCurrency(quotation.subtotal)}</span>
              </div>
              {quotation.discount > 0 && (
                <div className="flex justify-between text-sm text-red-600">
                  <span>Descuento:</span>
                  <span>-{formatCurrency(quotation.discount)}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-lg border-t pt-1.5">
                <span>Total:</span>
                <span className="text-pine-700">{formatCurrency(quotation.total)}</span>
              </div>
            </div>
          </div>

          {quotation.notes && (
            <div>
              <Label className="font-semibold text-sm text-slate-500">Notas</Label>
              <p className="text-sm mt-1">{quotation.notes}</p>
            </div>
          )}
          {quotation.payment_conditions && (
            <div>
              <Label className="font-semibold text-sm text-slate-500">Condiciones de Pago</Label>
              <p className="text-sm mt-1">{quotation.payment_conditions}</p>
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-2 border-t">
            <Button variant="outline" size="sm" onClick={() => onDownloadPdf(quotation._id)} data-testid="detail-download-pdf">
              <Download className="w-4 h-4 mr-2" /> Descargar PDF
            </Button>
            {quotation.status === 'pendiente' && (
              <>
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => onStatusChange(quotation._id, 'aceptada')} data-testid="accept-quotation-btn">
                  <CheckCircle className="w-4 h-4 mr-2" /> Aceptar
                </Button>
                <Button size="sm" variant="destructive" onClick={() => onStatusChange(quotation._id, 'rechazada')} data-testid="reject-quotation-btn">
                  <XCircle className="w-4 h-4 mr-2" /> Rechazar
                </Button>
              </>
            )}
            {(quotation.status === 'pendiente' || quotation.status === 'aceptada') && (
              <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => onOpenConvert(quotation)} data-testid="convert-to-sale-btn">
                <ShoppingCart className="w-4 h-4 mr-2" /> Convertir a Venta
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ConvertToSaleDialog({ open, onOpenChange, quotation, form, setForm, onConfirm, formatCurrency }) {
  if (!quotation) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Convertir a Venta</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="bg-green-50 p-4 rounded-lg text-center">
            <p className="text-sm text-green-700">Total de la cotizacion</p>
            <p className="text-2xl font-bold text-green-800">{formatCurrency(quotation.total)}</p>
          </div>
          <div className="space-y-2">
            <Label>Metodo de Pago</Label>
            <Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}>
              <SelectTrigger data-testid="convert-payment-method"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="efectivo">Efectivo</SelectItem>
                <SelectItem value="tarjeta">Tarjeta</SelectItem>
                <SelectItem value="transferencia">Transferencia</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Monto a pagar</Label>
            <Input
              type="number" min="0" step="0.01"
              value={form.amount_paid}
              onChange={(e) => setForm({ ...form, amount_paid: parseFloat(e.target.value) || 0 })}
              data-testid="convert-amount-paid"
            />
            {form.amount_paid < quotation.total && (
              <p className="text-xs text-amber-600">Saldo pendiente: {formatCurrency(quotation.total - form.amount_paid)}</p>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button className="bg-green-600 hover:bg-green-700" onClick={onConfirm} data-testid="confirm-convert-btn">
              <ShoppingCart className="w-4 h-4 mr-2" /> Confirmar Venta
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
