package app.opennaksha.core.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.opennaksha.R
import app.opennaksha.core.model.Badge
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.core.model.SchemeSummary
import app.opennaksha.core.model.Times
import app.opennaksha.core.model.badgeFor

@Composable
@ReadOnlyComposable
fun isGujarati(): Boolean = LocalConfiguration.current.locales[0].language == "gu"

/** Picks the name in the UI language, falling back to the other language. */
@Composable
@ReadOnlyComposable
fun localizedName(nameEn: String?, nameGu: String?): String? =
    if (isGujarati()) nameGu ?: nameEn else nameEn ?: nameGu

@Composable
@ReadOnlyComposable
fun schemeTitle(type: String, no: String): String = stringResource(R.string.scheme_title, type, no)

@Composable
@ReadOnlyComposable
fun SchemeSummary.displayName(): String {
    val title = schemeTitle(schemeType, schemeNo)
    return localizedName(nameEn, nameGu)?.let { "$title · $it" } ?: title
}

@Composable
@ReadOnlyComposable
fun SchemeRecord.displayName(): String {
    val title = schemeTitle(schemeType, schemeNo)
    return localizedName(nameEn, nameGu)?.let { "$title · $it" } ?: title
}

@Composable
@ReadOnlyComposable
fun statusLabel(status: String): String = stringResource(
    when (status) {
        "draft" -> R.string.status_draft
        "preliminary" -> R.string.status_preliminary
        "final" -> R.string.status_final
        "sanctioned_variation" -> R.string.status_sanctioned_variation
        else -> R.string.status_unknown
    },
)

/** Localized status plus the source site's own wording, e.g. "Draft (Submitted to Govt.)". */
@Composable
@ReadOnlyComposable
fun statusWithLabel(status: String, label: String?): String {
    val localized = statusLabel(status)
    return if (label.isNullOrBlank() || label.equals(localized, ignoreCase = true)) localized else "$localized ($label)"
}

@Composable
@ReadOnlyComposable
fun fileKindLabel(kind: String): String = stringResource(
    when (kind) {
        "map" -> R.string.file_kind_map
        "scheme_book" -> R.string.file_kind_scheme_book
        "notification" -> R.string.file_kind_notification
        "redistribution_statement" -> R.string.file_kind_redistribution_statement
        else -> R.string.file_kind_other
    },
)

@Composable
@ReadOnlyComposable
fun changeLabel(what: String): String = stringResource(
    when (what) {
        "map_file" -> R.string.what_map_file
        "other_file" -> R.string.what_other_file
        "status" -> R.string.what_status
        "name" -> R.string.what_name
        else -> R.string.what_new_file
    },
)

@Composable
fun BadgeChip(badge: Badge) {
    val (text, color) = when (badge) {
        Badge.NEW -> stringResource(R.string.badge_new) to MaterialTheme.colorScheme.primary
        Badge.UPDATED -> stringResource(R.string.badge_updated) to MaterialTheme.colorScheme.secondary
        Badge.REMOVED -> stringResource(R.string.badge_removed) to MaterialTheme.colorScheme.error
    }
    Surface(color = color, shape = MaterialTheme.shapes.small) {
        Text(
            text,
            color = Color.White,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
        )
    }
}

@Composable
fun SchemeRow(s: SchemeSummary, previousVisitMs: Long?, onClick: () -> Unit) {
    val badge = badgeFor(s.firstSeenMs, s.lastChangedMs, s.removedFromSource, previousVisitMs)
    val date = Times.formatDate(s.statusDate)
    ListItem(
        headlineContent = { Text(s.displayName()) },
        supportingContent = {
            Text(
                listOfNotNull(statusWithLabel(s.status, s.statusLabel), date, s.authority).joinToString(" · "),
                maxLines = 2,
            )
        },
        trailingContent = badge?.let { { BadgeChip(it) } },
        modifier = Modifier.fillMaxWidth().clickableRow(onClick),
    )
}

fun Modifier.clickableRow(onClick: () -> Unit): Modifier = this.clickable(onClick = onClick)

@Composable
fun BackButton(onBack: () -> Unit) {
    IconButton(onClick = onBack) {
        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
    }
}

@Composable
fun EmptyState(text: String, modifier: Modifier = Modifier, action: @Composable (() -> Unit)? = null) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyLarge)
        action?.invoke()
    }
}

@Composable
fun LabeledValue(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(0.4f))
        Text(value, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(0.6f))
    }
}

/** Opens a URL in the browser. Never crashes if no browser is installed. */
fun openUrl(context: Context, url: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, context.getString(R.string.error_no_app), Toast.LENGTH_SHORT).show()
    } catch (_: IllegalArgumentException) {
        Toast.makeText(context, context.getString(R.string.error_no_app), Toast.LENGTH_SHORT).show()
    }
}

fun startSafely(context: Context, intent: Intent) {
    try {
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, context.getString(R.string.error_no_app), Toast.LENGTH_SHORT).show()
    }
}

fun shareText(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    startSafely(context, Intent.createChooser(send, null))
}

/**
 * "Report a wrong/outdated map": a pre-filled email if `report_email` is set, else a GitHub issue
 * if `report_issues_url` is set; null when neither is configured (button hidden).
 */
fun reportIntent(context: Context, record: SchemeRecord): Intent? {
    val email = context.getString(R.string.report_email).trim()
    val issues = context.getString(R.string.report_issues_url).trim().trimEnd('/')
    val subject = context.getString(R.string.report_subject, record.id)
    val body = context.getString(R.string.report_body, record.id, record.sourcePageUrl)
    return when {
        email.isNotEmpty() -> Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:")).apply {
            putExtra(Intent.EXTRA_EMAIL, arrayOf(email))
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, body)
        }
        issues.isNotEmpty() -> Intent(
            Intent.ACTION_VIEW,
            Uri.parse("$issues/new").buildUpon()
                .appendQueryParameter("title", subject)
                .appendQueryParameter("body", body)
                .build(),
        )
        else -> null
    }
}
