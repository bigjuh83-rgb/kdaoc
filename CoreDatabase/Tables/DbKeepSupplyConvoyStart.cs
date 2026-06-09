using DOL.Database.Attributes;

namespace DOL.Database
{
	[DataTable(TableName = "KeepSupplyConvoyStart")]
	public class DbKeepSupplyConvoyStart : DataObject
	{
		public DbKeepSupplyConvoyStart()
		{
			Realm = 0;
			RegionID = 0;
			X = 0;
			Y = 0;
			Z = 0;
			Heading = 0;
		}

		[DataElement(AllowDbNull = false, Unique = true)]
		public int Realm { get; set; }

		[DataElement(AllowDbNull = false)]
		public int RegionID { get; set; }

		[DataElement(AllowDbNull = false)]
		public int X { get; set; }

		[DataElement(AllowDbNull = false)]
		public int Y { get; set; }

		[DataElement(AllowDbNull = false)]
		public int Z { get; set; }

		[DataElement(AllowDbNull = false)]
		public int Heading { get; set; }
	}
}
