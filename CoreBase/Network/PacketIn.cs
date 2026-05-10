using System;
using System.Buffers;
using System.IO;
using System.Text;

namespace DOL.Network
{
	/// <summary>
	/// Reads primitive data types from an underlying stream.
	/// </summary>
	public abstract class PacketIn : MemoryStream, IPacket
	{
		private static readonly Encoding StrictUtf8Encoding = new UTF8Encoding(false, true);
		private static readonly Encoding StrictDefaultEncoding = CreateStrictDefaultEncoding();

		protected PacketIn() { }

		protected PacketIn(int size) : base(size) { }

		public virtual PacketIn Init()
		{
			return this;
		}

		/// <summary>
		/// Generates a human-readable dump of the packet contents.
		/// </summary>
		/// <returns>a string representing the packet contents in hexadecimal</returns>
		public string ToHumanReadable()
		{
			return Marshal.ToHexDump(ToString(), ToArray());
		}

		/// <summary>
		/// Reads in 2 bytes and converts it from network to host byte order
		/// </summary>
		/// <returns>A 2 byte (short) value</returns>
		public ushort ReadShort()
		{
			var v1 = (byte) ReadByte();
			var v2 = (byte) ReadByte();

			return Marshal.ConvertToUInt16(v1, v2);
		}

		/// <summary>
		/// Reads in 2 bytes
		/// </summary>
		/// <returns>A 2 byte (short) value in network byte order</returns>
		public ushort ReadShortLowEndian()
		{
			var v1 = (byte) ReadByte();
			var v2 = (byte) ReadByte();

			return Marshal.ConvertToUInt16(v2, v1);
		}

		/// <summary>
		/// Reads in 4 bytes and converts it from network to host byte order
		/// </summary>
		/// <returns>A 4 byte value</returns>
		public uint ReadInt()
		{
			var v1 = (byte) ReadByte();
			var v2 = (byte) ReadByte();
			var v3 = (byte) ReadByte();
			var v4 = (byte) ReadByte();

			return Marshal.ConvertToUInt32(v1, v2, v3, v4);
		}

		/// <summary>
		/// Skips 'num' bytes ahead in the stream
		/// </summary>
		/// <param name="num">Number of bytes to skip ahead</param>
		public void Skip(long num)
		{
			Seek(num, SeekOrigin.Current);
		}

		/// <summary>
		/// Reads a null-terminated string from the stream
		/// </summary>
		/// <param name="maxlen">Maximum number of bytes to read in</param>
		/// <returns>A string of maxlen or less</returns>
		public string ReadString(int maxlen)
		{
			maxlen = GetReadableLength(maxlen);

			if (maxlen <= 0)
				return string.Empty;

			// Stack for small strings, ArrayPool for large strings.
			if (maxlen <= 1024)
			{
				Span<byte> buffer = stackalloc byte[maxlen];
				int bytesRead = Read(buffer);
				Span<byte> readBuffer = buffer[..bytesRead];
				int actualLength = readBuffer.IndexOf((byte) 0);

				if (actualLength == -1)
					actualLength = bytesRead;

				return BaseServer.DefaultEncoding.GetString(readBuffer[..actualLength]);
			}
			else
			{
				byte[] buffer = ArrayPool<byte>.Shared.Rent(maxlen);

				try
				{
					int bytesRead = Read(buffer, 0, maxlen);
					int actualLength = Array.IndexOf(buffer, (byte) 0, 0, bytesRead);

					if (actualLength == -1)
						actualLength = bytesRead;

					return BaseServer.DefaultEncoding.GetString(buffer, 0, actualLength);
				}
				finally
				{
					ArrayPool<byte>.Shared.Return(buffer);
				}
			}
		}

		/// <summary>
		/// Reads in a pascal style string
		/// </summary>
		/// <returns>A string from the stream</returns>
		public string ReadPascalString()
		{
			return ReadString(ReadByte());
		}

		/// <summary>
		/// Reads in a pascal style string, with header count formatted as a Low Endian Short.
		/// </summary>
		/// <returns>A string from the stream</returns>
		public string ReadShortPascalStringLowEndian()
		{
			return ReadString(ReadShortLowEndian());
		}

		public string ReadIntPascalStringLowEndian()
		{
			uint declaredLength = ReadIntLowEndian();
			int maxlen = GetReadableLength(declaredLength);

			if (maxlen <= 0)
				return string.Empty;

			if (maxlen <= 1024)
			{
				Span<byte> buffer = stackalloc byte[maxlen];
				int bytesRead = Read(buffer);
				Span<byte> readBuffer = buffer[..bytesRead];
				int actualLength = readBuffer.IndexOf((byte) 0);

				if (actualLength == -1)
					actualLength = bytesRead;

				return DecodeIntPascalString(readBuffer[..actualLength]);
			}

			byte[] rentedBuffer = ArrayPool<byte>.Shared.Rent(maxlen);

			try
			{
				int bytesRead = Read(rentedBuffer, 0, maxlen);
				int actualLength = Array.IndexOf(rentedBuffer, (byte) 0, 0, bytesRead);

				if (actualLength == -1)
					actualLength = bytesRead;

				return DecodeIntPascalString(rentedBuffer.AsSpan(0, actualLength));
			}
			finally
			{
				ArrayPool<byte>.Shared.Return(rentedBuffer);
			}
		}

		private int GetReadableLength(uint declaredLength)
		{
			long remaining = Length - Position;

			if (declaredLength == 0 || remaining <= 0)
				return 0;

			return (int) Math.Min(declaredLength, Math.Min(remaining, int.MaxValue));
		}

		private int GetReadableLength(int declaredLength)
		{
			if (declaredLength <= 0)
				return 0;

			return GetReadableLength((uint) declaredLength);
		}

		private static string DecodeIntPascalString(ReadOnlySpan<byte> bytes)
		{
			try
			{
				string utf8String = StrictUtf8Encoding.GetString(bytes);

				try
				{
					string defaultString = StrictDefaultEncoding.GetString(bytes);

					if (ShouldPreferDefaultEncoding(utf8String, defaultString))
						return defaultString;
				}
				catch (DecoderFallbackException)
				{
				}

				return utf8String;
			}
			catch (DecoderFallbackException)
			{
				return BaseServer.DefaultEncoding.GetString(bytes);
			}
		}

		private static Encoding CreateStrictDefaultEncoding()
		{
			Encoding encoding = (Encoding) BaseServer.DefaultEncoding.Clone();
			encoding.EncoderFallback = EncoderFallback.ExceptionFallback;
			encoding.DecoderFallback = DecoderFallback.ExceptionFallback;
			return encoding;
		}

		private static bool ShouldPreferDefaultEncoding(string utf8String, string defaultString)
		{
			return ContainsHangul(defaultString) && !ContainsHangul(utf8String);
		}

		private static bool ContainsHangul(string value)
		{
			foreach (char character in value)
			{
				if ((character >= '\uAC00' && character <= '\uD7AF')
					|| (character >= '\u1100' && character <= '\u11FF')
					|| (character >= '\u3130' && character <= '\u318F'))
				{
					return true;
				}
			}

			return false;
		}

		public uint ReadIntLowEndian()
		{
			var v1 = (byte) ReadByte();
			var v2 = (byte) ReadByte();
			var v3 = (byte) ReadByte();
			var v4 = (byte) ReadByte();

			return Marshal.ConvertToUInt32(v4, v3, v2, v1);
		}

		/// <summary>
		/// Reads low endian floats used in 1.124 packets
		/// </summary>
		/// <returns>converts it to a usable value</returns>
		public float ReadFloatLowEndian()
		{
			uint v = (uint) ((byte) ReadByte() | ((byte) ReadByte() << 8) | ((byte) ReadByte() << 16) | ((byte) ReadByte() << 24));
			return BitConverter.UInt32BitsToSingle(v);
		}

		/// <summary>
		/// Returns a <see cref="T:System.String"/> that represents the current <see cref="T:System.Object"/>.
		/// </summary>
		public override string ToString()
		{
			return GetType().Name;
		}

		public override void Close()
		{
			// Called by Dispose and normally invalidates the stream.
			// But this is both pointless (`MemoryStream` doesn't have any unmanaged resource) and undesirable (we always want the buffer to remain accessible)
		}
	}
}
