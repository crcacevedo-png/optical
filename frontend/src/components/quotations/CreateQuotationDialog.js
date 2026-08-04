/**
 * Dialogo "Nueva Cotizacion" extraido de QuotationsPage.js.
 * El estado (form, cart, search state, filters) permanece en la pagina padre;
 * este componente solo consume via props.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Search, CheckCircle, Package, Trash2, FileText } from 'lucide-react';

export function CreateQuotationDialog({
  open, onOpenChange, resetForm,
  form, setForm,
  patientSearch, setPatientSearch, filteredPatients, selectedPatientName,
  productSearch, setProductSearch, filteredProducts,
  cart, addToCart, updateCartItem, removeFromCart, cartSubtotal, cartTotal,
  onSubmit, formatCurrency,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) resetForm(); onOpenChange(o); }}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl">Nueva Cotizacion</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Patient Selection */}
          <div className="space-y-2">
            <Label className="font-semibold">Paciente *</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Buscar paciente por nombre o telefono..."
                value={patientSearch}
                onChange={(e) => setPatientSearch(e.target.value)}
                className="pl-9"
                data-testid="patient-search-input"
              />
            </div>
            {patientSearch && !form.patient_id && (
              <div className="border rounded-lg max-h-32 overflow-y-auto">
                {filteredPatients.slice(0, 5).map(p => (
                  <button
                    key={p._id}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex justify-between"
                    onClick={() => {
                      setForm({ ...form, patient_id: p._id });
                      setPatientSearch(`${p.first_name} ${p.last_name}`);
                    }}
                    data-testid={`select-patient-${p._id}`}
                  >
                    <span className="font-medium">{p.first_name} {p.last_name}</span>
                    <span className="text-slate-400">{p.phone}</span>
                  </button>
                ))}
              </div>
            )}
            {form.patient_id && selectedPatientName && (
              <div className="flex items-center gap-2 px-3 py-2 bg-pine-50 rounded-lg">
                <CheckCircle className="w-4 h-4 text-pine-600" />
                <span className="text-sm font-medium text-pine-800">{selectedPatientName.first_name} {selectedPatientName.last_name}</span>
                <Button variant="ghost" size="sm" className="ml-auto h-6 text-xs" onClick={() => { setForm({ ...form, patient_id: '' }); setPatientSearch(''); }}>
                  Cambiar
                </Button>
              </div>
            )}
          </div>

          {/* Products */}
          <div className="space-y-2">
            <Label className="font-semibold">Productos</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Buscar producto..."
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                className="pl-9"
                data-testid="product-search-input"
              />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto">
              {filteredProducts.slice(0, 12).map(p => (
                <button
                  key={p._id}
                  onClick={() => addToCart(p)}
                  className="p-2.5 border rounded-lg text-left hover:border-pine-300 hover:bg-pine-50 transition-colors"
                  data-testid={`add-product-${p._id}`}
                >
                  <div className="text-sm font-medium truncate">{p.name}</div>
                  <div className="text-xs text-slate-400">{p.sku}</div>
                  <div className="text-sm font-semibold text-pine-700 mt-1">{formatCurrency(p.sale_price)}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Cart */}
          {cart.length > 0 && (
            <div className="space-y-3">
              <Label className="font-semibold flex items-center gap-2">
                <Package className="w-4 h-4" /> Productos en cotizacion ({cart.length})
              </Label>
              <div className="border rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Producto</TableHead>
                      <TableHead className="w-24">Cant</TableHead>
                      <TableHead className="w-32">Precio Unit.</TableHead>
                      <TableHead className="w-28 text-right">Subtotal</TableHead>
                      <TableHead className="w-10"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cart.map((item, idx) => (
                      <TableRow key={item.product_id || `cart-${idx}`}>
                        <TableCell className="text-sm font-medium">{item.name}</TableCell>
                        <TableCell>
                          <Input
                            type="number" min="1"
                            value={item.quantity}
                            onChange={(e) => updateCartItem(idx, 'quantity', parseInt(e.target.value) || 1)}
                            className="h-8 w-20"
                            data-testid={`cart-qty-${idx}`}
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number" min="0" step="0.01"
                            value={item.unit_price}
                            onChange={(e) => updateCartItem(idx, 'unit_price', parseFloat(e.target.value) || 0)}
                            className="h-8 w-28"
                            data-testid={`cart-price-${idx}`}
                          />
                        </TableCell>
                        <TableCell className="text-right font-medium">{formatCurrency(item.subtotal)}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="sm" onClick={() => removeFromCart(idx)} className="text-red-500 h-7 w-7 p-0">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Totals */}
              <div className="flex justify-end">
                <div className="w-72 space-y-2 bg-slate-50 p-4 rounded-lg">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">Subtotal:</span>
                    <span className="font-medium">{formatCurrency(cartSubtotal)}</span>
                  </div>
                  <div className="flex justify-between text-sm items-center gap-2">
                    <span className="text-slate-500">Descuento:</span>
                    <Input
                      type="number" min="0" step="0.01"
                      value={form.discount}
                      onChange={(e) => setForm({ ...form, discount: parseFloat(e.target.value) || 0 })}
                      className="h-8 w-28 text-right"
                      data-testid="discount-input"
                    />
                  </div>
                  <div className="flex justify-between font-bold text-lg border-t pt-2">
                    <span>Total:</span>
                    <span className="text-pine-700">{formatCurrency(cartTotal)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Notes & Conditions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Notas</Label>
              <Textarea
                placeholder="Observaciones o detalles adicionales..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
                data-testid="notes-input"
              />
            </div>
            <div className="space-y-2">
              <Label>Condiciones de Pago</Label>
              <Textarea
                placeholder="Ej: 50% anticipo, 50% al entregar"
                value={form.payment_conditions}
                onChange={(e) => setForm({ ...form, payment_conditions: e.target.value })}
                rows={3}
                data-testid="payment-conditions-input"
              />
            </div>
          </div>

          {/* Validity */}
          <div className="w-48">
            <Label>Vigencia (dias)</Label>
            <Select value={String(form.validity_days)} onValueChange={(v) => setForm({ ...form, validity_days: parseInt(v) })}>
              <SelectTrigger data-testid="validity-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="7">7 dias</SelectItem>
                <SelectItem value="15">15 dias</SelectItem>
                <SelectItem value="30">30 dias</SelectItem>
                <SelectItem value="60">60 dias</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button
              onClick={onSubmit}
              className="bg-pine-700 hover:bg-pine-800"
              disabled={!form.patient_id || cart.length === 0}
              data-testid="save-quotation-btn"
            >
              <FileText className="w-4 h-4 mr-2" /> Crear Cotizacion
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
