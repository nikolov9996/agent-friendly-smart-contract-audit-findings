---
id: 25385
severity: "Medium"
---

# In function mint() and lzReceive(), _safeMint() is recommended over _mint(), which performs additional checks

## Description

Function [mint()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L60>) and [lzReceive()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L119>) mint a nft to a certain address, which may lead to lost tokens if _safeMint() is not used instead.

This recommendation should not apply to mintGenesis(), the proposed fixed there is using a Merkle Tree. Note: if lzReceive() reverts due to _safeMint(), the token is already burnt in the source chain, which could mean that the nft is forever lost.

However, if this happens, a minter can manually call safeMint() to the user (or another address specified by the user) in the destination chain.

Note that the endpoint's behavior is non blocking now by default, such that if the lzReceive reverts, other users may continue sending cross chain nfts [https://docs.layerzero.network/explore/layerzero-v2#improved-message-handling.](<https://docs.layerzero.network/explore/layerzero-v2#improved-message-handling>) mint() (or safeMint(), if the protocol fixes the usage of _mint()), should have a flag specifying if the nft is a genesis one, so if _safeMint() reverts on lzReceive(), it's still possible to mint the genesis nft.

Additionally, if lzReceive() fails, the owner must clear the payload beforehand in the [lzEndpoint](<https://github.com/LayerZero-Labs/LayerZero-v2/blob/main/protocol/contracts/EndpointV2.sol#L211>) manually if it wants to call safeMint() separately.

If a minter mints the lost token to the user before clearing the payload in the LzEndpoint, the user may act maliciously and send the newly minted token to another chain, burning it in the current chain, and then try to execute the payload again in the LzEndpoint, getting a free nft.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
