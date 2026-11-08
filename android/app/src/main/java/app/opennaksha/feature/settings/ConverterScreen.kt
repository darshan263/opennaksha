package app.opennaksha.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.core.model.LandUnit
import app.opennaksha.core.model.convertArea
import app.opennaksha.core.ui.BackButton
import java.text.NumberFormat

@Composable
private fun unitLabel(u: LandUnit): String = stringResource(
    when (u) {
        LandUnit.SQ_M -> R.string.unit_sq_m
        LandUnit.SQ_FT -> R.string.unit_sq_ft
        LandUnit.SQ_YARD -> R.string.unit_sq_yard
        LandUnit.GUNTHA -> R.string.unit_guntha
        LandUnit.VIGHA -> R.string.unit_vigha
        LandUnit.ACRE -> R.string.unit_acre
        LandUnit.HECTARE -> R.string.unit_hectare
    },
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConverterScreen(nav: NavController) {
    var input by rememberSaveable { mutableStateOf("1") }
    var from by rememberSaveable { mutableStateOf(LandUnit.GUNTHA) }
    var expanded by rememberSaveable { mutableStateOf(false) }
    val value = input.replace(",", "").toDoubleOrNull()
    val fmt = NumberFormat.getNumberInstance().apply { maximumFractionDigits = 4 }

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tools_converter)) }, navigationIcon = { BackButton { nav.popBackStack() } }) },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text(stringResource(R.string.converter_value)) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                isError = value == null,
                modifier = Modifier.fillMaxWidth(),
            )
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                OutlinedTextField(
                    value = unitLabel(from),
                    onValueChange = {},
                    readOnly = true,
                    label = { Text(stringResource(R.string.converter_from)) },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    LandUnit.entries.forEach { u ->
                        DropdownMenuItem(text = { Text(unitLabel(u)) }, onClick = { from = u; expanded = false })
                    }
                }
            }
            HorizontalDivider()
            LandUnit.entries.filter { it != from }.forEach { u ->
                ListItem(
                    headlineContent = { Text(value?.let { fmt.format(convertArea(it, from, u)) } ?: "—", style = MaterialTheme.typography.titleMedium) },
                    supportingContent = { Text(unitLabel(u)) },
                )
            }
            Text(
                stringResource(R.string.converter_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
