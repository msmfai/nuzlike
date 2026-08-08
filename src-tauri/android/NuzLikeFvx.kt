// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
package org.nuzlike.patcher

import android.content.Context
import com.uprfvx.random.nuzlike.NuzLikeBridge
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.PrintStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

/** Android/ART adapter for the same FVX bridge used by desktop packages. */
object NuzLikeFvx {
    @JvmStatic
    @Synchronized
    fun randomize(context: Context, input: ByteArray, settings: String, seed: Long): ByteArray {
        val workspace = File(context.cacheDir, "nuzlike-fvx-${UUID.randomUUID()}")
        return try {
            check(workspace.mkdir()) { "cannot create the private FVX workspace" }
            val source = File(workspace, "clean.rom")
            val randomized = File(workspace, "randomized.rom")
            val manifest = File(workspace, "manifest.json")
            val log = File(workspace, "randomizer.log")
            source.writeBytes(input)

            val errors = ByteArrayOutputStream()
            val previousError = System.err
            val status = try {
                System.setErr(PrintStream(errors, true, Charsets.UTF_8.name()))
                NuzLikeBridge.invoke(arrayOf(
                    "-i", source.absolutePath,
                    "-o", randomized.absolutePath,
                    "-S", settings,
                    "-z", seed.toString(),
                    "--manifest", manifest.absolutePath,
                    "--log", log.absolutePath,
                ))
            } finally {
                System.setErr(previousError)
            }
            check(status == 0) {
                errors.toString(Charsets.UTF_8.name()).trim().ifEmpty {
                    "FVX exited with status $status"
                }
            }

            val manifestBytes = manifest.readBytes()
            val logBytes = log.readBytes()
            val randomizedBytes = randomized.readBytes()
            ByteBuffer.allocate(9 + manifestBytes.size + logBytes.size + randomizedBytes.size)
                .order(ByteOrder.BIG_ENDIAN)
                .put(0.toByte())
                .putInt(manifestBytes.size)
                .putInt(logBytes.size)
                .put(manifestBytes)
                .put(logBytes)
                .put(randomizedBytes)
                .array()
        } catch (error: Throwable) {
            val detail = (error.message ?: error.javaClass.simpleName).toByteArray(Charsets.UTF_8)
            byteArrayOf(1) + detail
        } finally {
            workspace.deleteRecursively()
        }
    }
}
