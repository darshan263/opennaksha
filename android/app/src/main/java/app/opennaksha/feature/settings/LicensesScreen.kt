package app.opennaksha.feature.settings

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.core.ui.BackButton

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicensesScreen(nav: NavController) {
    // Each entry: "Name|License"
    val libs = stringArrayResource(R.array.licenses_list).map { it.substringBefore('|') to it.substringAfter('|') }
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.settings_licenses)) }, navigationIcon = { BackButton { nav.popBackStack() } }) },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize()) {
            item {
                Text(stringResource(R.string.licenses_intro), modifier = Modifier.padding(16.dp))
            }
            items(libs) { (name, license) ->
                ListItem(headlineContent = { Text(name) }, supportingContent = { Text(license) })
            }
            item {
                Text(
                    stringResource(R.string.licenses_osm_notice),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }
    }
}
