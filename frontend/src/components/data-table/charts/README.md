# Charts

In order to maintain a consistent look and feel across all charts, we have a few components that are used to build the charts.

## Components

#### layouts
Thin wrappers around @ui components that provide consistent styling and behavior.

#### form-fields
Form fields that are used for chart forms. Wraps react-hook-form components

#### chart-items
Components that are used to build the charts. Groups together common form fields and layouts.

## Context

To keep each component light and avoid prop drilling, we can either use react-hook-form's `useFormContext` or `use` to access shared state (`context.ts`).


Layouts:
 - TabContainer
 - AccordionConfigs
 

Chart Components:
 - ChartTypeSelect
 - XAxis
 - YAxis
 - ColorByAxis
 - Facet

Forms:
 - CommonChartForm
 - PieForm
 - BarForm
 - LineForm
 - ScatterForm
 - AreaForm
 - HeatmapForm
 - Style Form

Field Components:
 - ColumnSelector
 - DataTypeSelect
 - AggregationSelect
 - TooltipSelect
 - BooleanField
 - NumberField
 - SliderField
 - ColorArrayField
 - TimeUnitSelect
 - SelectField

<TabContainer>
    <TabsContent value="data">
        <FormSection>
            <FieldSection>
            </FieldSection>
        </FormSection>
    </TabsContent>
    <TabsContent value="style">
        <StyleForm />
    </TabsContent>
</TabContainer>