package app.opennaksha.core.model

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/** Parsing/formatting of the catalog's ISO-8601 timestamps and dates. */
object Times {
    /** Epoch millis of an ISO timestamp ("2026-11-15T02:00:00Z") or date ("2024-03-12"); 0 if invalid. */
    fun millis(value: String?): Long {
        if (value.isNullOrBlank()) return 0
        return runCatching { Instant.parse(value).toEpochMilli() }
            .recoverCatching { LocalDate.parse(value).atStartOfDay(ZoneId.of("UTC")).toInstant().toEpochMilli() }
            .getOrDefault(0)
    }

    fun formatDate(value: String?, locale: Locale = Locale.getDefault()): String? {
        val ms = millis(value).takeIf { it > 0 } ?: return null
        return formatDate(ms, locale)
    }

    fun formatDate(millis: Long, locale: Locale = Locale.getDefault()): String =
        DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).withLocale(locale)
            .format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

    fun formatDateTime(millis: Long, locale: Locale = Locale.getDefault()): String =
        DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT).withLocale(locale)
            .format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

    /** Calendar day (local time) of a timestamp, for grouping. */
    fun localDay(value: String): LocalDate =
        Instant.ofEpochMilli(millis(value)).atZone(ZoneId.systemDefault()).toLocalDate()
}

/** Natural sort key for scheme numbers: "2" < "2A" < "10". */
fun naturalKey(s: String): List<Comparable<*>> =
    Regex("""\d+|\D+""").findAll(s).map { m ->
        m.value.toLongOrNull() ?: m.value.lowercase()
    }.toList()

val NaturalOrder: Comparator<String> = Comparator { a, b ->
    val ka = naturalKey(a)
    val kb = naturalKey(b)
    for (i in 0 until minOf(ka.size, kb.size)) {
        val x = ka[i]
        val y = kb[i]
        val c = when {
            x is Long && y is Long -> x.compareTo(y)
            x is Long -> -1
            y is Long -> 1
            else -> (x as String).compareTo(y as String)
        }
        if (c != 0) return@Comparator c
    }
    ka.size.compareTo(kb.size)
}

/** Compares dotted versions numerically ("0.10.0" > "0.9.1"). Non-numeric parts count as 0. */
fun compareVersions(a: String, b: String): Int {
    val pa = a.trim().removePrefix("v").split('.', '-').map { it.toIntOrNull() ?: 0 }
    val pb = b.trim().removePrefix("v").split('.', '-').map { it.toIntOrNull() ?: 0 }
    for (i in 0 until maxOf(pa.size, pb.size)) {
        val c = (pa.getOrElse(i) { 0 }).compareTo(pb.getOrElse(i) { 0 })
        if (c != 0) return c
    }
    return 0
}
